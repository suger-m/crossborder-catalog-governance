from __future__ import annotations

import json
import shutil
from pathlib import Path

from openpyxl import Workbook
from reportlab.pdfgen import canvas

def build_fixture(target: Path) -> list[Path]:
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    image = target / "lookbook-front.jpg"
    shutil.copy2(Path(__file__).with_name("cc0-dress.jpg"), image)

    workbook_path = target / "supplier-catalog.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "商品主数据"
    headers = [
        " 款号 ", "SKU ID", "商品名称", "描述", "品类", "款式", "面料", "纤维含量",
        "洗涤说明", "原产国", "品牌", "颜色", "尺码", "条码", "价格", "库存",
        "图片", "标签", "卖点", "认证",
    ]
    sheet.append(headers)
    rows = []
    for color, sizes in (("Black", ("Ｓ", "M", "L")), ("Ivory", ("S", "M", "L"))):
        for index, size in enumerate(sizes, start=1):
            rows.append([
                "CC0-DRESS-100", f"CDR-{color[:3].upper()}-{size}", "Women's Structured Midi Dress",
                "A structured midi dress designed for office and everyday wear.", "Dresses", "Midi Dress",
                "Cotton；Elastane", "95% Cotton / 5% Elastane", "Machine wash cold", "中国",
                "River & Willow", color, size, f"880100{len(rows):06d}", "US$ 79.90",
                "1,200 pcs" if len(rows) == 0 else str(18 + index), "lookbook-front.jpg",
                "work；minimal", "comfortable fit", "",
            ])
    for color in ("Navy", "Cream"):
        for size in ("M", "L"):
            rows.append([
                "SUPPLIER-KNIT-200", f"SKN-{color[:3].upper()}-{size}", "Women's Wool Blend Cardigan",
                "Soft button-front cardigan designed for layering.", "Women’s Tops", "Cardigan", "Wool, Nylon",
                "", "Hand wash cold", "Viet Nam", "River & Willow", color, size, f"880200{len(rows):06d}",
                "$49.50", "25件", "https://example.com/supplier-knit-200.jpg", "layering, knitwear",
                "soft wool blend", "",
            ])
    for row in rows:
        sheet.append(row)
    notes = workbook.create_sheet("供应商说明")
    notes.append(["说明", "值"])
    notes.append(["更新时间", "2026-08-15"])
    notes.append(["币种", "USD"])
    workbook.save(workbook_path)

    pdf_path = target / "label-specification.pdf"
    document = canvas.Canvas(str(pdf_path))
    y = 790
    for line in (
        "Product ID: CC0-DRESS-100",
        "Country of Origin: Vietnam",
        "Fiber Content: 95% cotton; 5% elastane",
        "Care Instructions: Machine wash cold",
        "Manufacturer: River & Willow",
    ):
        document.drawString(72, y, line)
        y -= 22
    document.showPage()
    y = 790
    for line in (
        "Product ID: SUPPLIER-KNIT-200",
        "Country of Origin: VN",
        "Care Instructions: Hand wash cold",
        "Manufacturer: River & Willow",
    ):
        document.drawString(72, y, line)
        y -= 22
    document.save()

    metadata_path = target / "media-and-certifications.json"
    metadata_path.write_text(
        json.dumps(
            {
                "products": [
                    {
                        "product_id": "CC0-DRESS-100",
                        "images": ["lookbook-front.jpg", "https://example.com/cc0-dress-100-detail.jpg"],
                        "certifications": ["OEKO-TEX Standard 100"],
                        "tags": ["office", "midi"],
                    },
                    {
                        "product_id": "SUPPLIER-KNIT-200",
                        "images": ["https://example.com/rw-knit-200-detail.jpg"],
                        "certifications": [],
                        "tags": ["cardigan", "layering"],
                    },
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return [workbook_path, pdf_path, metadata_path, image]
