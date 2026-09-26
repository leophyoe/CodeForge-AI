from __future__ import annotations

from .models import RAGConfig, SourceReference


class ContextBuilder:
    def __init__(self, config: RAGConfig | None = None) -> None:
        self.config = config or RAGConfig()

    def build_context(
        self,
        search_results: list[dict],
        max_tokens: int | None = None,
    ) -> tuple[str, list[SourceReference]]:
        max_tokens = max_tokens or self.config.max_context_tokens
        sources: list[SourceReference] = []
        context_parts: list[str] = []
        current_tokens = 0

        for result in search_results:
            content = result.get("content", "")
            if not content:
                continue

            chunk_tokens = max(1, len(content) // 4)
            if current_tokens + chunk_tokens > max_tokens:
                remaining = max_tokens - current_tokens
                if remaining > 100:
                    content = content[: remaining * 4]
                    chunk_tokens = remaining
                else:
                    break

            source = SourceReference(
                file_path=result.get("relative_path", ""),
                start_line=result.get("start_line", 0),
                end_line=result.get("end_line", 0),
                symbol=result.get("symbol_name", ""),
                chunk_id=result.get("chunk_id", ""),
                score=result.get("score", 0.0),
            )
            sources.append(source)

            part = (
                f"[Source {len(sources)}]\n"
                f"Path: {source.file_path}\n"
                f"Lines: {source.start_line}-{source.end_line}\n"
                f"Symbol: {source.symbol or 'N/A'}\n"
                f"```\n{content}\n```\n"
            )
            context_parts.append(part)
            current_tokens += chunk_tokens

        return "\n".join(context_parts), sources

    def build_prompt(
        self,
        query: str,
        context: str,
        system_prompt: str | None = None,
    ) -> list[dict]:
        system = system_prompt or self.config.system_prompt

        messages = [
            {"role": "system", "content": system},
        ]

        if context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "RETRIEVED REPOSITORY CONTEXT:\n\n"
                        "The following code snippets were retrieved from the repository. "
                        "Use them to answer the user's question. "
                        "Cite sources using [Source N] format.\n\n"
                        f"{context}"
                    ),
                }
            )

        messages.append({"role": "user", "content": query})
        return messages

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
