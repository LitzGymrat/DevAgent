"""
Phase 2A 路由测评：基座 + LoRA（单文件，可拷到 AutoDL 单独跑）。

默认路径与旧 eval_lora.py 一致风格；用 --base-model / --lora-path / --test-data 覆盖。
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer

DEFAULT_BASE_MODEL = "/root/autodl-tmp/models/qwen/Qwen2.5-7B-Instruct"
DEFAULT_LORA_PATH = "/root/LLaMA-Factory/saves/Qwen2-7B-Instruct/lora/train_2026-03-12-05-39-51"
DEFAULT_TEST_DATA = "/root/LLaMA-Factory/data/devagent_phase2a_eval.json"


def _resolve_pretrained_source(path_or_id: str) -> str:
    """
    本地权重路径转成绝对路径，避免 Peft 把「含斜杠的相对路径」当成 Hub 的 org/repo。
    HuggingFace id（如 Qwen/Qwen2.5-7B-Instruct）在磁盘上不存在，原样返回。
    """
    p = Path(path_or_id).expanduser()
    if p.exists():
        return str(p.resolve())
    resolved = p.resolve()
    if resolved.exists():
        return str(resolved)
    return path_or_id


def _load_causal_lm(path_or_id: str) -> PreTrainedModel:
    kw = dict(device_map="auto", trust_remote_code=True)
    try:
        return AutoModelForCausalLM.from_pretrained(
            path_or_id, dtype=torch.bfloat16, **kw
        )
    except TypeError:
        return AutoModelForCausalLM.from_pretrained(
            path_or_id, torch_dtype=torch.bfloat16, **kw
        )

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


def transformers_generate_reply(
    tokenizer: PreTrainedTokenizer,
    model: PreTrainedModel,
    case: dict[str, Any],
    *,
    max_new_tokens: int = 512,
    temperature: float = 0.1,
    do_sample: bool = False,
) -> str:
    message = [
        {"role": "system", "content": case["conversations"][0]["value"]},
        {"role": "user", "content": case["conversations"][1]["value"]},
    ]
    text = tokenizer.apply_chat_template(
        message, tokenize=False, add_generation_prompt=True
    )
    model_input = tokenizer([text], return_tensors="pt").to(model.device)
    with torch.no_grad():
        generated_ids = model.generate(
            **model_input,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=do_sample,
        )
    output_ids = [
        out[len(inp) :] for inp, out in zip(model_input.input_ids, generated_ids)
    ]
    return tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 2A routing eval — LoRA")
    ap.add_argument("--base-model", type=str, default=DEFAULT_BASE_MODEL)
    ap.add_argument(
        "--lora-path",
        type=str,
        default=DEFAULT_LORA_PATH,
        help="LoRA 适配器目录，建议绝对路径，例如 /root/LLaMA-Factory/saves/.../lora/run_id",
    )
    ap.add_argument(
        "--test-data",
        type=Path,
        default=Path(DEFAULT_TEST_DATA),
        help="ShareGPT JSON 数组",
    )
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--temperature", type=float, default=0.1)
    args = ap.parse_args()

    base_model = _resolve_pretrained_source(args.base_model)
    lora_path = _resolve_pretrained_source(args.lora_path)
    print("正在加载分词器、基座并挂载 LoRA…")
    print(f"  base_model = {base_model}\n  lora_path  = {lora_path}\n")

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    model = _load_causal_lm(base_model)
    model = PeftModel.from_pretrained(model, lora_path)
    model.eval()

    with args.test_data.open("r", encoding="utf-8") as f:
        test_cases = json.load(f)

    m = Phase2aMetrics(n_file_rows=len(test_cases))
    print(f"====== DevAgent Phase 2A · LoRA · {len(test_cases)} 条 ======\n")

    for _i, case in enumerate(tqdm(test_cases, desc="lora")):
        gold = gold_from_sharegpt_case(case)
        if gold is None:
            m.skipped_bad_gold += 1
            continue
        raw = transformers_generate_reply(
            tokenizer,
            model,
            case,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            do_sample=False,
        )
        pred = parse_routing_json(raw) if raw else None
        m.update(gold, pred)

    for line in m.report_lines():
        print(line)


if __name__ == "__main__":
    main()
