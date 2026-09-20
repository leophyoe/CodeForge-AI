from __future__ import annotations

import re

from .models import ImportKind, ImportReference, Symbol, SymbolKind


class SymbolExtractor:
    def extract_symbols(
        self,
        source: bytes,
        language: str,
        file_id: str = "",
        workspace_id: str = "",
    ) -> list[Symbol]:
        try:
            text = source.decode("utf-8", errors="replace")
        except Exception:
            return []

        lines = text.split("\n")
        symbols: list[Symbol] = []

        if language == "python":
            symbols = self._extract_python(lines, file_id, workspace_id)
        elif language in ("javascript", "typescript"):
            symbols = self._extract_js_ts(lines, language, file_id, workspace_id)
        elif language == "java":
            symbols = self._extract_java(lines, file_id, workspace_id)
        elif language == "go":
            symbols = self._extract_go(lines, file_id, workspace_id)
        elif language == "rust":
            symbols = self._extract_rust(lines, file_id, workspace_id)
        elif language in ("c", "cpp"):
            symbols = self._extract_c_cpp(lines, language, file_id, workspace_id)
        elif language == "csharp":
            symbols = self._extract_csharp(lines, file_id, workspace_id)
        elif language == "ruby":
            symbols = self._extract_ruby(lines, file_id, workspace_id)
        elif language == "php":
            symbols = self._extract_php(lines, file_id, workspace_id)
        elif language == "bash":
            symbols = self._extract_bash(lines, file_id, workspace_id)

        return symbols

    def _extract_python(
        self, lines: list[str], file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        current_class: str = ""
        class_indent = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            class_match = re.match(r"^class\s+(\w+)", stripped)
            if class_match:
                name = class_match.group(1)
                current_class = name
                class_indent = indent
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=name,
                        kind=SymbolKind.CLASS,
                        language="python",
                        start_line=i,
                        end_line=i,
                        qualified_name=name,
                    )
                )
                continue

            if current_class and indent <= class_indent and stripped:
                current_class = ""

            func_match = re.match(r"^(?:async\s+)?def\s+(\w+)\s*\(", stripped)
            if func_match:
                name = func_match.group(1)
                kind = SymbolKind.METHOD if current_class else SymbolKind.FUNCTION
                parent_id = ""
                if current_class:
                    for s in reversed(symbols):
                        if s.name == current_class and s.kind == SymbolKind.CLASS:
                            parent_id = s.symbol_id
                            break
                qualified = f"{current_class}.{name}" if current_class else name
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=name,
                        kind=kind,
                        language="python",
                        start_line=i,
                        end_line=i,
                        parent_symbol_id=parent_id,
                        qualified_name=qualified,
                    )
                )

        return symbols

    def _extract_js_ts(
        self, lines: list[str], language: str, file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        current_class = ""

        for i, line in enumerate(lines):
            stripped = line.strip()

            class_match = re.match(r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", stripped)
            if class_match:
                name = class_match.group(1)
                current_class = name
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=name,
                        kind=SymbolKind.CLASS,
                        language=language,
                        start_line=i,
                        end_line=i,
                        qualified_name=name,
                    )
                )
                continue

            if language == "typescript":
                iface_match = re.match(r"^(?:export\s+)?interface\s+(\w+)", stripped)
                if iface_match:
                    symbols.append(
                        Symbol(
                            file_id=file_id,
                            workspace_id=workspace_id,
                            name=iface_match.group(1),
                            kind=SymbolKind.INTERFACE,
                            language=language,
                            start_line=i,
                            end_line=i,
                            qualified_name=iface_match.group(1),
                        )
                    )
                    continue

                type_match = re.match(r"^(?:export\s+)?type\s+(\w+)", stripped)
                if type_match:
                    symbols.append(
                        Symbol(
                            file_id=file_id,
                            workspace_id=workspace_id,
                            name=type_match.group(1),
                            kind=SymbolKind.TYPE,
                            language=language,
                            start_line=i,
                            end_line=i,
                            qualified_name=type_match.group(1),
                        )
                    )
                    continue

                enum_match = re.match(r"^(?:export\s+)?enum\s+(\w+)", stripped)
                if enum_match:
                    symbols.append(
                        Symbol(
                            file_id=file_id,
                            workspace_id=workspace_id,
                            name=enum_match.group(1),
                            kind=SymbolKind.ENUM,
                            language=language,
                            start_line=i,
                            end_line=i,
                            qualified_name=enum_match.group(1),
                        )
                    )
                    continue

            func_match = re.match(
                r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)", stripped
            )
            if func_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=func_match.group(1),
                        kind=SymbolKind.FUNCTION,
                        language=language,
                        start_line=i,
                        end_line=i,
                        qualified_name=func_match.group(1),
                    )
                )
                continue

            method_match = re.match(r"^\s+(?:async\s+)?(\w+)\s*\(", line)
            if method_match and current_class:
                name = method_match.group(1)
                if name not in ("if", "for", "while", "switch", "catch", "return"):
                    symbols.append(
                        Symbol(
                            file_id=file_id,
                            workspace_id=workspace_id,
                            name=name,
                            kind=SymbolKind.METHOD,
                            language=language,
                            start_line=i,
                            end_line=i,
                            qualified_name=f"{current_class}.{name}",
                        )
                    )

        return symbols

    def _extract_java(
        self, lines: list[str], file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            class_match = re.match(
                r"^(?:public|private|protected)?\s*(?:abstract\s+)?(?:static\s+)?class\s+(\w+)",
                stripped,
            )
            if class_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=class_match.group(1),
                        kind=SymbolKind.CLASS,
                        language="java",
                        start_line=i,
                        end_line=i,
                        qualified_name=class_match.group(1),
                    )
                )
                continue

            iface_match = re.match(r"^(?:public|private|protected)?\s*interface\s+(\w+)", stripped)
            if iface_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=iface_match.group(1),
                        kind=SymbolKind.INTERFACE,
                        language="java",
                        start_line=i,
                        end_line=i,
                        qualified_name=iface_match.group(1),
                    )
                )
                continue

            method_match = re.match(
                r"^(?:public|private|protected)?\s*(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\(",
                stripped,
            )
            if method_match:
                name = method_match.group(1)
                if name not in ("if", "for", "while", "switch", "catch", "return"):
                    symbols.append(
                        Symbol(
                            file_id=file_id,
                            workspace_id=workspace_id,
                            name=name,
                            kind=SymbolKind.METHOD,
                            language="java",
                            start_line=i,
                            end_line=i,
                            qualified_name=name,
                        )
                    )

        return symbols

    def _extract_go(
        self, lines: list[str], file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            func_match = re.match(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)", stripped)
            if func_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=func_match.group(1),
                        kind=SymbolKind.FUNCTION,
                        language="go",
                        start_line=i,
                        end_line=i,
                        qualified_name=func_match.group(1),
                    )
                )
                continue

            struct_match = re.match(r"^type\s+(\w+)\s+struct", stripped)
            if struct_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=struct_match.group(1),
                        kind=SymbolKind.STRUCT,
                        language="go",
                        start_line=i,
                        end_line=i,
                        qualified_name=struct_match.group(1),
                    )
                )
                continue

            iface_match = re.match(r"^type\s+(\w+)\s+interface", stripped)
            if iface_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=iface_match.group(1),
                        kind=SymbolKind.INTERFACE,
                        language="go",
                        start_line=i,
                        end_line=i,
                        qualified_name=iface_match.group(1),
                    )
                )

        return symbols

    def _extract_rust(
        self, lines: list[str], file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            fn_match = re.match(r"^(?:pub\s+)?fn\s+(\w+)", stripped)
            if fn_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=fn_match.group(1),
                        kind=SymbolKind.FUNCTION,
                        language="rust",
                        start_line=i,
                        end_line=i,
                        qualified_name=fn_match.group(1),
                    )
                )
                continue

            struct_match = re.match(r"^(?:pub\s+)?struct\s+(\w+)", stripped)
            if struct_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=struct_match.group(1),
                        kind=SymbolKind.STRUCT,
                        language="rust",
                        start_line=i,
                        end_line=i,
                        qualified_name=struct_match.group(1),
                    )
                )
                continue

            enum_match = re.match(r"^(?:pub\s+)?enum\s+(\w+)", stripped)
            if enum_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=enum_match.group(1),
                        kind=SymbolKind.ENUM,
                        language="rust",
                        start_line=i,
                        end_line=i,
                        qualified_name=enum_match.group(1),
                    )
                )
                continue

            trait_match = re.match(r"^(?:pub\s+)?trait\s+(\w+)", stripped)
            if trait_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=trait_match.group(1),
                        kind=SymbolKind.INTERFACE,
                        language="rust",
                        start_line=i,
                        end_line=i,
                        qualified_name=trait_match.group(1),
                    )
                )

        return symbols

    def _extract_c_cpp(
        self, lines: list[str], language: str, file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            struct_match = re.match(r"^(?:typedef\s+)?(?:struct|union|enum)\s+(\w+)", stripped)
            if struct_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=struct_match.group(1),
                        kind=SymbolKind.STRUCT,
                        language=language,
                        start_line=i,
                        end_line=i,
                        qualified_name=struct_match.group(1),
                    )
                )
                continue

            func_match = re.match(
                r"^(?:static\s+)?(?:inline\s+)?(?:\w+\s+)+(\w+)\s*\(", stripped
            )
            if func_match:
                name = func_match.group(1)
                if name not in ("if", "for", "while", "switch", "return"):
                    symbols.append(
                        Symbol(
                            file_id=file_id,
                            workspace_id=workspace_id,
                            name=name,
                            kind=SymbolKind.FUNCTION,
                            language=language,
                            start_line=i,
                            end_line=i,
                            qualified_name=name,
                        )
                    )

        return symbols

    def _extract_csharp(
        self, lines: list[str], file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            class_match = re.match(
                r"^(?:public|private|protected|internal)?\s*(?:abstract\s+)?class\s+(\w+)",
                stripped,
            )
            if class_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=class_match.group(1),
                        kind=SymbolKind.CLASS,
                        language="csharp",
                        start_line=i,
                        end_line=i,
                        qualified_name=class_match.group(1),
                    )
                )
                continue

            method_match = re.match(
                r"^(?:public|private|protected|internal)\s+(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(",
                stripped,
            )
            if method_match:
                name = method_match.group(1)
                if name not in ("if", "for", "while", "switch", "return"):
                    symbols.append(
                        Symbol(
                            file_id=file_id,
                            workspace_id=workspace_id,
                            name=name,
                            kind=SymbolKind.METHOD,
                            language="csharp",
                            start_line=i,
                            end_line=i,
                            qualified_name=name,
                        )
                    )

        return symbols

    def _extract_ruby(
        self, lines: list[str], file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            class_match = re.match(r"^class\s+(\w+)", stripped)
            if class_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=class_match.group(1),
                        kind=SymbolKind.CLASS,
                        language="ruby",
                        start_line=i,
                        end_line=i,
                        qualified_name=class_match.group(1),
                    )
                )
                continue

            module_match = re.match(r"^module\s+(\w+)", stripped)
            if module_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=module_match.group(1),
                        kind=SymbolKind.MODULE,
                        language="ruby",
                        start_line=i,
                        end_line=i,
                        qualified_name=module_match.group(1),
                    )
                )
                continue

            func_match = re.match(r"^def\s+(?:self\.)?(\w+)", stripped)
            if func_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=func_match.group(1),
                        kind=SymbolKind.METHOD,
                        language="ruby",
                        start_line=i,
                        end_line=i,
                        qualified_name=func_match.group(1),
                    )
                )

        return symbols

    def _extract_php(
        self, lines: list[str], file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            class_match = re.match(r"^(?:abstract\s+)?class\s+(\w+)", stripped)
            if class_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=class_match.group(1),
                        kind=SymbolKind.CLASS,
                        language="php",
                        start_line=i,
                        end_line=i,
                        qualified_name=class_match.group(1),
                    )
                )
                continue

            method_match = re.match(
                r"^(?:public|private|protected)\s+function\s+(\w+)", stripped
            )
            if method_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=method_match.group(1),
                        kind=SymbolKind.METHOD,
                        language="php",
                        start_line=i,
                        end_line=i,
                        qualified_name=method_match.group(1),
                    )
                )

        return symbols

    def _extract_bash(
        self, lines: list[str], file_id: str, workspace_id: str
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            func_match = re.match(r"^(\w+)\s*\(\s*\)", stripped)
            if func_match:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=func_match.group(1),
                        kind=SymbolKind.FUNCTION,
                        language="bash",
                        start_line=i,
                        end_line=i,
                        qualified_name=func_match.group(1),
                    )
                )
                continue

            func_match2 = re.match(r"^function\s+(\w+)", stripped)
            if func_match2:
                symbols.append(
                    Symbol(
                        file_id=file_id,
                        workspace_id=workspace_id,
                        name=func_match2.group(1),
                        kind=SymbolKind.FUNCTION,
                        language="bash",
                        start_line=i,
                        end_line=i,
                        qualified_name=func_match2.group(1),
                    )
                )

        return symbols

    def extract_imports(
        self,
        source: bytes,
        language: str,
        file_id: str = "",
        workspace_id: str = "",
    ) -> list[ImportReference]:
        try:
            text = source.decode("utf-8", errors="replace")
        except Exception:
            return []

        lines = text.split("\n")
        imports: list[ImportReference] = []
        patterns = self._get_import_patterns(language)

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//")):
                continue

            for pattern, kind_str in patterns:
                match = re.match(pattern, stripped)
                if match:
                    groups = match.groups()
                    import_path = groups[0] if groups else ""
                    imported_names: list[str] = []

                    if kind_str == "from_import" and len(groups) > 1:
                        names_str = groups[1]
                        imported_names = [
                            n.strip().split(" as ")[0].strip()
                            for n in names_str.split(",")
                            if n.strip()
                        ]

                    kind = ImportKind.IMPORT
                    if kind_str == "from_import":
                        kind = ImportKind.FROM_IMPORT
                    elif kind_str == "require":
                        kind = ImportKind.REQUIRE
                    elif kind_str == "dynamic_import":
                        kind = ImportKind.DYNAMIC_IMPORT

                    imports.append(
                        ImportReference(
                            file_id=file_id,
                            workspace_id=workspace_id,
                            import_path=import_path,
                            import_kind=kind,
                            imported_names=imported_names,
                            line=i,
                        )
                    )
                    break

        return imports

    def _get_import_patterns(self, language: str) -> list[tuple[str, str]]:
        from .parser import RegexParser

        parser = RegexParser()
        return parser.IMPORT_PATTERNS.get(language, [])

    def extract_exports(
        self,
        source: bytes,
        language: str,
        file_id: str = "",
        workspace_id: str = "",
    ) -> list[dict]:
        if language not in ("javascript", "typescript"):
            return []

        try:
            text = source.decode("utf-8", errors="replace")
        except Exception:
            return []

        exports: list[dict] = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            stripped = line.strip()
            export_match = re.match(
                r"^export\s+(?:default\s+)?(?:function|class|const|let|var|interface|type|enum)\s+(\w+)",
                stripped,
            )
            if export_match:
                exports.append(
                    {
                        "export_name": export_match.group(1),
                        "line": i,
                        "file_id": file_id,
                        "workspace_id": workspace_id,
                    }
                )
                continue

            named_match = re.match(r"^export\s+\{([^}]+)\}", stripped)
            if named_match:
                names = [
                    n.strip().split(" as ")[0].strip()
                    for n in named_match.group(1).split(",")
                ]
                for name in names:
                    if name:
                        exports.append(
                            {
                                "export_name": name,
                                "line": i,
                                "file_id": file_id,
                                "workspace_id": workspace_id,
                            }
                        )

        return exports
