# External LLM Reviews

This folder stores external-model review prompts and responses for methodology/spec audits.

## File Naming Pattern

- Prompt: `reviews/prompt_<topic>_<version>.txt`
- Claude output: `reviews/claude_<topic>_<version>_review.txt`
- Gemini output: `reviews/gemini_<topic>_<version>_review.txt`
- Provider stderr logs: same name with `.err.txt`

## Current Artifacts

- `reviews/prompt_metrics_v1.txt`
- `reviews/claude_metrics_v1_review.txt`
- `reviews/gemini_metrics_v1_review.txt`
- `reviews/prompt_metrics_methodology_v2.txt`
- `reviews/claude_metrics_methodology_v2_review.txt`
- `reviews/gemini_metrics_methodology_v2_review.txt`
- `reviews/codex_metrics_methodology_v2_review.md`

## Standard Workflow

1. Build a single shared prompt file that includes the exact files under review.
2. Run both providers against the same prompt.
3. Save raw outputs and stderr logs to this folder.
4. Reconcile findings in repo notes/specs (do not overwrite provider outputs).

## Commands

Claude:

```sh
claude -p "$(cat reviews/prompt_metrics_methodology_v2.txt)" \
  > reviews/claude_metrics_methodology_v2_review.txt \
  2> reviews/claude_metrics_methodology_v2_review.err.txt
```

Gemini:

```sh
gemini -m gemini-3-pro-preview -p "$(cat reviews/prompt_metrics_methodology_v2.txt)" \
  > reviews/gemini_metrics_methodology_v2_review.txt \
  2> reviews/gemini_metrics_methodology_v2_review.err.txt
```

If shell argument length/quoting is an issue, use piped stdin:

```sh
cat reviews/prompt_metrics_methodology_v2.txt | claude -p \
  > reviews/claude_metrics_methodology_v2_review.txt \
  2> reviews/claude_metrics_methodology_v2_review.err.txt

cat reviews/prompt_metrics_methodology_v2.txt | gemini -m gemini-3-pro-preview -p \
  > reviews/gemini_metrics_methodology_v2_review.txt \
  2> reviews/gemini_metrics_methodology_v2_review.err.txt
```

## Prompt Requirements

- Ask for structured output sections (must-fix, should-fix, metric add/remove, methodology validity, next steps).
- Request metric IDs and concrete implementation guidance.
- Use the same prompt for both providers to keep comparisons fair.
