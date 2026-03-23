"""
Phase 2A 路由测评：OpenAI 兼容 API（单文件，可拷到 AutoDL 单独跑）。

金标：assistant 为单行 JSON（decision_type / tool_name / arguments / …）。

配置优先级：
  1) 环境变量：OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_MODEL（或 DEEPSEEK_*）
  2) 若在 DevAgent 仓库根目录且存在 .env：from src.config import settings
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI
from tqdm import tqdm

# ---------- 与 AutoDL / LLaMA-Factory 常见布局一致；可用 --test-data 覆盖 ----------
DEFAULT_TEST_DATA = "/root/LLaMA-Factory/data/devagent_phase2a_eval.json"

ALLOWED_TOOLS = frozenset(
    {
        "analyse_code",
        "complete_code",
        "generate_tests",
        "generate_dockerfile",
        "analyse_log",
        "search_codebase",
    }
)
ALLOWED_DECISIONS = frozenset({"tool_call", "no_tool", "clarify_needed"})
_FENCE = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)


def _strip_markdown_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = _FENCE.sub("", t)
        if t.endswith("```"):
            t = t[:-3].strip()
    return t


def parse_routing_json(text: str) -> dict[str, Any] | None:
    if not text or not text.strip():
        return None
    candidates = [text.strip(), _strip_markdown_fence(text)]
    decoder = json.JSONDecoder()
    for chunk in candidates:
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            obj = json.loads(chunk)
            if isinstance(obj, dict) and "decision_type" in obj:
                return obj
        except json.JSONDecodeError:
            pass
        i = 0
        while i < len(chunk):
            j = chunk.find("{", i)
            if j < 0:
                break
            try:
                obj, _end = decoder.raw_decode(chunk, j)
                if isinstance(obj, dict) and obj.get("decision_type") in ALLOWED_DECISIONS:
                    return obj
            except json.JSONDecodeError:
                pass
            i = j + 1
    return None


def is_valid_phase2a_shape(obj: dict[str, Any]) -> bool:
    dt = obj.get("decision_type")
    if dt not in ALLOWED_DECISIONS:
        return False
    if dt == "tool_call":
        tn = obj.get("tool_name")
        return isinstance(tn, str) and tn in ALLOWED_TOOLS
    if dt == "no_tool":
        return obj.get("tool_name") is None and obj.get("arguments") is None
    if dt == "clarify_needed":
        ca = obj.get("clarify_answer")
        return isinstance(ca, str) and bool(ca.strip())
    return False


def gold_from_sharegpt_case(case: dict[str, Any]) -> dict[str, Any] | None:
    try:
        gold_str = case["conversations"][2]["value"]
        g = json.loads(gold_str)
        if not isinstance(g, dict) or g.get("decision_type") not in ALLOWED_DECISIONS:
            return None
        return g
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None


def _norm_arguments(a: Any) -> Any:
    if a is None:
        return None
    if isinstance(a, dict):
        return json.dumps(a, sort_keys=True, ensure_ascii=False)
    return a


def arguments_equal(gold: dict[str, Any], pred: dict[str, Any]) -> bool:
    return _norm_arguments(gold.get("arguments")) == _norm_arguments(pred.get("arguments"))


@dataclass
class Phase2aMetrics:
    n_file_rows: int = 0
    skipped_bad_gold: int = 0
    n_evaluated: int = 0
    n_parse: int = 0
    n_parse_valid_shape: int = 0
    n_decision_match: int = 0
    n_gold_tool_call: int = 0
    n_tool_match: int = 0
    n_args_match: int = 0
    n_hallucination_tool: int = 0

    def update(self, gold: dict[str, Any], pred: dict[str, Any] | None) -> None:
        self.n_evaluated += 1
        if pred is None:
            return
        self.n_parse += 1
        if is_valid_phase2a_shape(pred):
            self.n_parse_valid_shape += 1
        if pred.get("decision_type") == gold.get("decision_type"):
            self.n_decision_match += 1
        if gold.get("decision_type") == "tool_call":
            self.n_gold_tool_call += 1
            if (
                pred.get("decision_type") == "tool_call"
                and pred.get("tool_name") == gold.get("tool_name")
            ):
                self.n_tool_match += 1
                if arguments_equal(gold, pred):
                    self.n_args_match += 1
        if pred.get("decision_type") == "tool_call":
            tn = pred.get("tool_name")
            if tn is None or tn not in ALLOWED_TOOLS:
                self.n_hallucination_tool += 1

    def report_lines(self) -> list[str]:
        g = max(self.n_evaluated, 1)
        gc = max(self.n_gold_tool_call, 1)
        return [
            "====== Phase 2A 路由测评 ======",
            f"样本总数（文件条数）: {self.n_file_rows}",
            f"金标可解析条数: {self.n_evaluated}（跳过金标损坏: {self.skipped_bad_gold}）",
            f"模型输出可解析为 JSON: {self.n_parse} ({100 * self.n_parse / g:.3f}%)",
            f"解析且角色字段合法: {self.n_parse_valid_shape} ({100 * self.n_parse_valid_shape / g:.3f}%)",
            f"decision_type 一致: {self.n_decision_match} ({100 * self.n_decision_match / g:.3f}%)",
            f"金标为 tool_call 的条数: {self.n_gold_tool_call}",
            f"tool_call 子集·工具名一致: {self.n_tool_match} ({100 * self.n_tool_match / gc:.3f}% of gold tool_call)",
            f"tool_call 子集·工具+arguments 一致: {self.n_args_match} ({100 * self.n_args_match / gc:.3f}% of gold tool_call)",
            f"预测 tool_call 但工具名非法/空: {self.n_hallucination_tool}（越低越好）",
            "=" * 50,
        ]


def _openai_client_and_model() -> tuple[OpenAI, str]:
    """仓库内用 src.config；拷到服务器单跑时用环境变量（见文件头说明）。"""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("DEEPSEEK_BASE_URL")
    model = os.environ.get("OPENAI_MODEL") or os.environ.get("DEEPSEEK_MODEL_NAME")
    if api_key:
        base_url = base_url or "https://api.deepseek.com"
        model = model or "deepseek-chat"
        return OpenAI(api_key=api_key, base_url=base_url), model
    try:
        from src.config import settings

        return (
            OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            ),
            settings.model_name,
        )
    except ImportError:
        pass
    raise SystemExit(
        "无法加载 API 配置：请在仓库根目录运行（使用 .env + src.config），或设置环境变量：\n"
        "  OPENAI_API_KEY（或 DEEPSEEK_API_KEY）\n"
        "  OPENAI_BASE_URL（或 DEEPSEEK_BASE_URL），例如 https://api.deepseek.com\n"
        "  OPENAI_MODEL（或 DEEPSEEK_MODEL_NAME），例如 deepseek-chat"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 2A routing eval — API")
    ap.add_argument(
        "--test-data",
        type=Path,
        default=Path(DEFAULT_TEST_DATA),
        help="ShareGPT JSON 数组路径",
    )
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--max-tokens", type=int, default=512)
    args = ap.parse_args()

    client, model_name = _openai_client_and_model()
    with args.test_data.open("r", encoding="utf-8") as f:
        test_cases = json.load(f)

    m = Phase2aMetrics(n_file_rows=len(test_cases))
    print("====== DevAgent Phase 2A · API 测评 ======\n")

    for i, case in enumerate(tqdm(test_cases, desc="api")):
        gold = gold_from_sharegpt_case(case)
        if gold is None:
            m.skipped_bad_gold += 1
            continue
        messages = [
            {"role": "system", "content": case["conversations"][0]["value"]},
            {"role": "user", "content": case["conversations"][1]["value"]},
        ]
        try:
            response = client.chat.completions.create(
                model=model_name,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                messages=messages,
            )
            raw = (response.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"[warn] 第 {i + 1} 条 API 失败: {e}")
            raw = ""
        pred = parse_routing_json(raw) if raw else None
        m.update(gold, pred)

    for line in m.report_lines():
        print(line)


if __name__ == "__main__":
    main()
