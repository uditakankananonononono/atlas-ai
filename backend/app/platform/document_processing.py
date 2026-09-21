"""Real PDF/OCR/layout processing with explicit confidence and provenance."""
from __future__ import annotations
from pathlib import Path
from typing import Any

def extract_pdf(path:str,*,ocr:bool=False)->dict[str,Any]:
 import fitz
 document=fitz.open(path);pages=[]
 for number,page in enumerate(document):
  text=page.get_text('text').strip();method='pymupdf'
  if ocr and not text:
   import pytesseract
   from PIL import Image
   pix=page.get_pixmap(matrix=fitz.Matrix(2,2));text=pytesseract.image_to_string(Image.frombytes('RGB',[pix.width,pix.height],pix.samples));method='tesseract'
  pages.append({'page':number+1,'text':text,'method':method})
 return {'path':str(Path(path)),'pages':pages,'page_count':len(pages),'requires_review':any(not x['text'].strip() for x in pages)}
def partition_layout(path:str):
 from unstructured.partition.auto import partition
 return [{'type':type(x).__name__,'text':str(x),'metadata':x.metadata.to_dict()} for x in partition(filename=path)]
