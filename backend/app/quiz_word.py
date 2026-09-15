from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .schemas import QuizExportRequest


def _run(text: str, *, bold: bool = False, color: str = "17202A", size: int = 22) -> str:
    properties = f'<w:rPr>{"<w:b/>" if bold else ""}<w:color w:val="{color}"/><w:sz w:val="{size}"/></w:rPr>'
    return f'<w:r>{properties}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _paragraph(text: str = "", *, bold: bool = False, color: str = "17202A", size: int = 22, before: int = 0, after: int = 120) -> str:
    return f'<w:p><w:pPr><w:spacing w:before="{before}" w:after="{after}"/></w:pPr>{_run(text, bold=bold, color=color, size=size)}</w:p>'


def build_quiz_docx(payload: QuizExportRequest) -> bytes:
    body: list[str] = []
    body.append(_paragraph("ORVIX", bold=True, color="078D84", size=28, after=80))
    body.append(_paragraph(payload.title, bold=True, color="111827", size=34, after=120))
    label = "Questions à choix multiple" if payload.quiz_type == "multiple_choice" else "Questions traditionnelles"
    body.append(_paragraph(f"Format : {label}  |  Nombre de questions : {len(payload.questions)}", color="657286", size=19, after=180))
    body.append(_paragraph("Nom de l'étudiant : ____________________________________    Date : __________________", size=20, after=260))
    body.append(_paragraph("QUESTIONNAIRE", bold=True, color="078D84", size=24, after=160))

    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for index, item in enumerate(payload.questions, start=1):
        body.append(_paragraph(f"{index}. {item.question}", bold=True, size=22, before=120, after=110))
        if payload.quiz_type == "multiple_choice":
            for choice_index, choice in enumerate(item.choices):
                body.append(_paragraph(f"   ☐ {letters[choice_index]}. {choice}", size=20, after=65))
        else:
            for _ in range(4):
                body.append(_paragraph("________________________________________________________________________________", color="A5AFB8", size=18, after=75))

    body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    body.append(_paragraph("CORRIGÉ", bold=True, color="078D84", size=28, after=180))
    for index, item in enumerate(payload.questions, start=1):
        if payload.quiz_type == "multiple_choice" and 0 <= item.answer_index < len(item.choices):
            answer = f"{letters[item.answer_index]}. {item.choices[item.answer_index]}"
        else:
            answer = item.expected_answer or "Réponse à développer selon le cours."
        body.append(_paragraph(f"Question {index}", bold=True, size=21, before=100, after=60))
        body.append(_paragraph(f"Réponse : {answer}", bold=True, color="245E59", size=20, after=60))
        body.append(_paragraph(item.explanation, color="52616D", size=19, after=130))

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{''.join(body)}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080"/></w:sectPr></w:body></w:document>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
    return output.getvalue()
