from config.llm_config import llm
from db.chroma_helper import search_index
from schema.boilerplate_schema import GenerateBoilerplateRequest, BoilerplateEdits
from langchain_core.prompts import ChatPromptTemplate

# MOCK_CONTEXT = """
# Company Coding Standards:

# 1. All functions must have type hints
# 2. Use async/await for all I/O operations
# 3. Error handling must use custom exception classes, not generic Exception
# 4. All API responses must follow the format: {"data": ..., "error": null} or {"data": null, "error": "message"}
# 5. Variable names must be snake_case
# 6. No print statements, use logging module instead
# """


def strip_code_fences(text: str) -> str:
    lines = text.strip().splitlines()
    if not lines:
        return text
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


async def run_generate_boilerplate(request: GenerateBoilerplateRequest) -> BoilerplateEdits:
    selection_note = (
        f"The user highlighted this region as the focus of the change:\n{request.selection_context}"
        if request.selection_context
        else ""
    )

    file_note = (
        f"Here is the full current file:\n{request.file_content}"
        if request.file_content
        else "The file is currently empty."
    )

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a code editor for {language}. You are given a file and an instruction, and you produce the set of edits that carry out the instruction while strictly following these company coding standards:\n\n"
                "{context}\n\n"
                "{file_note}\n\n"
                "{selection_note}\n\n"
                "Return a list of edits. Each edit has two fields:\n"
                "- `search`: the exact block of existing code to replace, copied VERBATIM from the file above (same text, same indentation). To ADD new code, set `search` to the exact existing line you will anchor on and repeat that line unchanged at the start of `replace`. If the file is empty or there is no sensible anchor, set `search` to an empty string.\n"
                "- `replace`: the code that should take the place of `search`, following the standards. Preserve the existing function names, variable names, exports, and signatures EXACTLY — do NOT rename anything unless the instruction explicitly asks. Do NOT write import statements — assume they are added automatically; reference symbols directly by name. Output only the code that belongs at the edit site — do NOT re-emit file-level scaffolding that already exists in the file (module/package/namespace declarations, class or component wrappers, top-level markup) unless the request is explicitly to create a whole new file. No markdown code fences, no explanations.\n\n"
                "Write `search` and `replace` as plain text with REAL line breaks. Never escape a newline as a backslash followed by the letter n — the field must contain actual newline characters, not that two-character sequence.\n\n"
                "Emit an edit for EVERY location the change affects — scan the WHOLE file and do not stop at the obvious ones. If the instruction touches more than one place (a function AND its callers, a declaration AND everything that references it, or a rename), you MUST include an edit for each occurrence, including event handlers, attributes, and repeated usages. A `search` that matches several IDENTICAL locations is fine — it is applied to ALL of them, so do NOT try to make such a search unique or add surrounding context to disambiguate repeated lines; just emit that search once.\n\n"
                "If the standards include examples in multiple languages, only use the {language} implementation.",
            ),
            ("human", "{prompt}"),
        ]
    )

    context = await search_index(request.query)

    structured_llm = llm.with_structured_output(BoilerplateEdits)
    chain = template | structured_llm
    result = await chain.ainvoke(
        {
            "context": context,
            "prompt": request.query,
            "language": request.language,
            "file_note": file_note,
            "selection_note": selection_note,
        }
    )

    # with_structured_output returns a BoilerplateEdits; strip any stray fences the
    # model may have wrapped a `replace` in.
    result = BoilerplateEdits.model_validate(result)
    for edit in result.edits:
        edit.replace = strip_code_fences(edit.replace)
    return result
