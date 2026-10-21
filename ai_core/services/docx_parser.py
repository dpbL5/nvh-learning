import os
import zipfile
import re
try:
    from defusedxml import ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
import tempfile
import subprocess
import hashlib
import mimetypes
import shutil
from typing import List, Dict, Any, Optional, Tuple
from django.conf import settings
from django.core.files.base import ContentFile
from exams.models import ImageBank

# Thư mục lưu trữ cố định cho ảnh render từ WMF/PNG của ImageBank
IMAGE_BANK_DIR = os.path.join(settings.MEDIA_ROOT, 'questions', 'images', 'bank')
MAX_DOCX_FILE_BYTES = 25 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024

# Namespaces chuẩn của DOCX
NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'v': 'urn:schemas-microsoft-com:vml',
    'o': 'urn:schemas-microsoft-com:office:office',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture'
}

# Highlight color IDs theo OOXML spec
HIGHLIGHT_COLORS = {
    'yellow', 'green', 'cyan', 'magenta', 'blue', 'red',
    'darkblue', 'darkred', 'darkgreen', 'darkcyan', 'darkmagenta',
    'darkgray', 'lightgray', 'none'
}


class DocxNativeParser:
    """
    Parser bóc tách file DOCX theo dạng Content Blocks, giữ nguyên thứ tự xuất hiện của chữ và ảnh.
    V2: Hỗ trợ đọc formatting (bold, underline, highlight) và bảng đáp án cuối đề.
    """

    @classmethod
    def parse_docx(cls, docx_path: str) -> List[Dict[str, Any]]:
        """
        Đọc file DOCX, trả về list các content_blocks (text + image).
        Metadata: bold, underline, highlight được gắn vào từng block text để AI nhận diện đáp án đúng.
        """
        # os.makedirs(IMAGE_BANK_DIR, exist_ok=True)  # Disabled for Vercel Serverless
        if os.path.getsize(docx_path) > MAX_DOCX_FILE_BYTES:
            raise ValueError('File DOCX vượt quá dung lượng cho phép.')

        with zipfile.ZipFile(docx_path, 'r') as zf:
            if sum(info.file_size for info in zf.infolist()) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ValueError('Nội dung DOCX giải nén vượt quá giới hạn cho phép.')
            rels_map = cls._build_relationships_map(zf)
            doc_xml = zf.read('word/document.xml')
            root = ET.fromstring(doc_xml)
            body = root.find('w:body', NS)
            blocks = []

            for elem in body:
                tag = elem.tag

                if tag == f"{{{NS['w']}}}p":
                    para_blocks = cls._parse_paragraph(elem, zf, rels_map)
                    if para_blocks:
                        if blocks and blocks[-1]['type'] == 'text':
                            blocks[-1]['value'] += '\n'
                        elif blocks:
                            blocks.append({'type': 'text', 'value': '\n'})
                        blocks.extend(para_blocks)

                elif tag == f"{{{NS['w']}}}tbl":
                    # Parse bảng ra dạng structured text — để AI hiểu bảng đáp án
                    tbl_content = cls._parse_table(elem, zf, rels_map)
                    if tbl_content:
                        blocks.append({'type': 'text', 'value': '\n' + tbl_content + '\n'})

        merged = cls._merge_adjacent_text_blocks(blocks)
        return merged

    @staticmethod
    def _build_relationships_map(zf: zipfile.ZipFile) -> Dict[str, str]:
        """Đọc word/_rels/document.xml.rels để ánh xạ rId -> path trong ZIP"""
        rels_map = {}
        try:
            rels_xml = zf.read('word/_rels/document.xml.rels')
            root = ET.fromstring(rels_xml)
            rel_ns = {'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}
            for rel in root.findall('rel:Relationship', rel_ns):
                r_id = rel.get('Id')
                target = rel.get('Target')
                if not r_id or not target:
                    continue

                normalized_target = target.replace('\\', '/').lstrip('/')
                if normalized_target.startswith('../'):
                    normalized_target = normalized_target[3:]

                if normalized_target.startswith('word/'):
                    zip_member = normalized_target
                elif normalized_target.startswith('media/'):
                    zip_member = f"word/{normalized_target}"
                elif '/media/' in normalized_target:
                    zip_member = f"word/media/{normalized_target.split('/media/', 1)[1]}"
                else:
                    continue

                rels_map[r_id] = zip_member
        except KeyError:
            pass
        return rels_map

    @classmethod
    def _get_run_formatting(cls, run: ET.Element) -> Dict[str, bool]:
        """
        Đọc các thuộc tính định dạng quan trọng của <w:r> để xác định đáp án đúng.
        Returns: { bold, underline, highlight, strikethrough }
        """
        rpr = run.find('w:rPr', NS)
        if rpr is None:
            return {}

        fmt = {}

        # Bold: <w:b/> hoặc <w:b w:val="true"/>
        b = rpr.find('w:b', NS)
        if b is not None:
            val = b.get(f"{{{NS['w']}}}val", 'true')
            fmt['bold'] = val.lower() not in ('false', '0', 'off')

        # Underline: <w:u w:val="single|double|wave|..."/>
        u = rpr.find('w:u', NS)
        if u is not None:
            uval = u.get(f"{{{NS['w']}}}val", 'single')
            fmt['underline'] = uval.lower() not in ('none', 'false', '0')

        # Highlight: <w:highlight w:val="yellow|green|cyan|..."/>
        hl = rpr.find('w:highlight', NS)
        if hl is not None:
            hl_color = hl.get(f"{{{NS['w']}}}val", '').lower()
            if hl_color and hl_color != 'none':
                fmt['highlight'] = True
                fmt['highlight_color'] = hl_color

        # Color: Một số đề để đáp án đúng màu đỏ / xanh
        color_el = rpr.find('w:color', NS)
        if color_el is not None:
            color_val = color_el.get(f"{{{NS['w']}}}val", '').lower()
            # Đỏ (FF0000), Xanh lam (0000FF), Xanh lá (00B050), v.v.
            if color_val not in ('auto', '000000', 'ffffff', ''):
                fmt['color'] = color_val

        # Strikethrough: <w:strike/>
        strike = rpr.find('w:strike', NS)
        if strike is not None:
            fmt['strikethrough'] = True

        return fmt

    @classmethod
    def _parse_paragraph(cls, p_elem: ET.Element, zf: zipfile.ZipFile, rels_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Duyệt từng <w:r> trong 1 <w:p>, bóc text kèm formatting metadata và ảnh."""
        blocks = []

        for run in p_elem.findall('w:r', NS):
            fmt = cls._get_run_formatting(run)

            # 1. Text runs
            t_elems = run.findall('w:t', NS)
            for t_elem in t_elems:
                if t_elem is not None and t_elem.text:
                    block = {'type': 'text', 'value': t_elem.text}
                    if fmt:
                        block['fmt'] = fmt
                    blocks.append(block)

            # 2. VML (WMF/OLE) images: <w:pict>
            for pict in run.findall('w:pict', NS):
                for shape in pict.findall('.//v:shape', NS):
                    imagedata = shape.find('v:imagedata', NS)
                    if imagedata is not None:
                        r_id = None
                        for key, val in imagedata.attrib.items():
                            if key.endswith('}id') or key == 'id':
                                r_id = val
                                break
                        if r_id and r_id in rels_map:
                            style_str = shape.get('style', '')
                            w_pt, h_pt = cls._parse_style_size(style_str)
                            img_block = cls._process_image_to_bank(zf, rels_map[r_id], w_pt, h_pt)
                            if img_block:
                                blocks.append(img_block)

            # 3. DrawingML (PNG/JPG): <w:drawing>
            for drawing in run.findall('w:drawing', NS):
                for blip in drawing.findall('.//a:blip', NS):
                    r_id = blip.get(f"{{{NS['r']}}}embed")
                    if r_id and r_id in rels_map:
                        extent = drawing.find('.//wp:extent', {'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'})
                        w_pt, h_pt = None, None
                        if extent is not None:
                            cx = int(extent.get('cx', 0))
                            cy = int(extent.get('cy', 0))
                            w_pt = round(cx / 12700.0, 2)
                            h_pt = round(cy / 12700.0, 2)
                        img_block = cls._process_image_to_bank(zf, rels_map[r_id], w_pt, h_pt)
                        if img_block:
                            blocks.append(img_block)

        return blocks

    @classmethod
    def _parse_table(cls, tbl_elem: ET.Element, zf: zipfile.ZipFile, rels_map: Dict[str, Any]) -> str:
        """
        Parse bảng DOCX thành chuỗi text có cấu trúc dạng:
        [BẢNG] | Cell1 | Cell2 | Cell3 |
        ...
        Giúp AI nhận diện bảng đáp án cuối đề kiểu:
        Câu | 1 | 2 | 3 | 4 |
        Đáp án | A | B | C | D |
        """
        rows_text = []
        for row in tbl_elem.findall('.//w:tr', NS):
            cells = row.findall('.//w:tc', NS)
            cell_texts = []
            for cell in cells:
                # Lấy toàn bộ text trong cell (kể cả định dạng bold)
                parts = []
                for p in cell.findall('.//w:p', NS):
                    para_blocks = cls._parse_paragraph(p, zf, rels_map)
                    para_text = ''.join(
                        b['value'] for b in para_blocks if b['type'] == 'text'
                    ).strip()
                    if para_text:
                        parts.append(para_text)
                cell_texts.append(' '.join(parts))
            if any(cell_texts):
                rows_text.append('| ' + ' | '.join(cell_texts) + ' |')

        if not rows_text:
            return ''

        # Kiểm tra xem có phải bảng đáp án không
        header = rows_text[0].lower() if rows_text else ''
        is_answer_table = any(kw in header for kw in ['câu', 'đáp án', 'answer', 'question', 'đề'])
        prefix = '[BẢNG ĐÁP ÁN]\n' if is_answer_table else '[BẢNG]\n'

        return prefix + '\n'.join(rows_text)

    @staticmethod
    def _parse_style_size(style_str: str):
        """Parse width:10pt;height:20pt từ chuỗi style VML"""
        w_pt, h_pt = None, None
        if not style_str: return w_pt, h_pt
        w_match = re.search(r'width:([\d.]+)pt', style_str)
        h_match = re.search(r'height:([\d.]+)pt', style_str)
        if w_match: w_pt = float(w_match.group(1))
        if h_match: h_pt = float(h_match.group(1))
        return w_pt, h_pt

    @classmethod
    def _process_image_to_bank(cls, zf: zipfile.ZipFile, zip_path: str, w_pt: float, h_pt: float) -> Optional[Dict[str, Any]]:
        """
        Chiết xuất ảnh từ DOCX ZIP, nếu là WMF thì convert.
        Tính SHA-256, lưu vào ImageBank DB.
        """
        try:
            img_bytes = zf.read(zip_path)
            if len(img_bytes) > MAX_IMAGE_BYTES:
                print(f"  Skip oversized image: {zip_path}")
                return None
            ext = os.path.splitext(zip_path)[1].lower()

            if ext in ['.wmf', '.emf']:
                converted_bytes = cls._convert_metafile_to_png(img_bytes, ext)
                if not converted_bytes:
                    print(f"  Skip {ext.upper()} image (cannot convert on serverless): {zip_path}")
                    return None
                if len(converted_bytes) > MAX_IMAGE_BYTES:
                    print(f"  Skip oversized converted image: {zip_path}")
                    return None
                img_bytes = converted_bytes
                ext = '.png'

            sha256_hash = hashlib.sha256(img_bytes).hexdigest()
            mime_type = mimetypes.guess_type(f"file{ext}")[0] or 'application/octet-stream'
            base_name = os.path.basename(zip_path)

            img_bank, created = ImageBank.objects.get_or_create(
                sha256=sha256_hash,
                defaults={
                    'original_filename': base_name,
                    'mime_type': mime_type,
                    'file_size': len(img_bytes),
                    'width_pt': w_pt,
                    'height_pt': h_pt
                }
            )

            from ai_core.services.cloudinary_service import upload_to_cloudinary
            needs_upload = False

            if created:
                needs_upload = True
            else:
                if not img_bank.image_file or not img_bank.image_file.name.startswith('http'):
                    needs_upload = True

            if needs_upload:
                file_name = f"{sha256_hash}{ext}"
                cloudinary_res = upload_to_cloudinary(img_bytes, file_name)
                secure_url = cloudinary_res.get('secure_url') if cloudinary_res else None
                if secure_url:
                    img_bank.image_file.name = secure_url
                    img_bank.image_url = secure_url
                    img_bank.cloudinary_public_id = cloudinary_res.get('public_id') or img_bank.cloudinary_public_id
                    img_bank.save()
                elif settings.DEBUG:
                    img_bank.image_file.save(f"{sha256_hash}{ext}", ContentFile(img_bytes), save=True)
                else:
                    if created:
                        img_bank.delete()
                    print(f"  Cloudinary upload failed for {zip_path}")
                    return None

            if not created and not img_bank.original_filename:
                img_bank.original_filename = base_name
                img_bank.save()

            print(f"  Processed image: {zip_path} -> SHA256: {sha256_hash[:8]}...")
            
            # Since img_bank.image_file could be a direct URL or local path
            url_to_return = ''
            if img_bank.image_file:
                url_to_return = img_bank.image_file.name if img_bank.image_file.name.startswith('http') else img_bank.image_file.url

            return {
                'type': 'image',
                'sha256': sha256_hash,
                'width_pt': w_pt,
                'height_pt': h_pt,
                'url': url_to_return
            }

        except Exception as e:
            print(f"  Error extracting image {zip_path}: {e}")
            return None

    @staticmethod
    def _convert_metafile_to_png(meta_bytes: bytes, ext: str) -> Optional[bytes]:
        """Convert WMF/EMF -> PNG bằng ImageMagick hoặc LibreOffice."""
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                in_path = os.path.join(tmp_dir, f'input{ext}')
                out_path = os.path.join(tmp_dir, 'output.png')
                with open(in_path, 'wb') as f:
                    f.write(meta_bytes)

                commands = []
                if shutil.which('magick'):
                    commands.append(['magick', in_path, out_path])
                if shutil.which('convert'):
                    commands.append(['convert', in_path, out_path])
                if shutil.which('soffice'):
                    commands.append(['soffice', '--headless', '--convert-to', 'png', '--outdir', tmp_dir, in_path])

                for cmd in commands:
                    try:
                        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
                        candidate = out_path
                        if cmd[0] == 'soffice':
                            candidate = os.path.join(tmp_dir, 'input.png')
                        if os.path.exists(candidate):
                            with open(candidate, 'rb') as out_file:
                                return out_file.read()
                    except Exception:
                        continue
        except Exception:
            return None
        return None

    @classmethod
    def _merge_adjacent_text_blocks(cls, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Gộp các block text liền nhau CÙNG formatting thành 1 block.
        Các block khác formatting không được gộp lại.
        """
        if not blocks:
            return []

        merged = []
        for b in blocks:
            if not merged:
                merged.append(b.copy())
                continue

            last = merged[-1]
            # Chỉ gộp nếu cả 2 đều là text và cùng fmt
            if (last['type'] == 'text' and b['type'] == 'text'
                    and last.get('fmt') == b.get('fmt')
                    and not str(last.get('value', '')).endswith('\n')
                    and not str(b.get('value', '')).startswith('\n')):
                last['value'] += b['value']
            else:
                merged.append(b.copy())

        # Dọn dẹp: bỏ block text chỉ toàn whitespace không có ý nghĩa
        result = []
        for b in merged:
            if b['type'] == 'image':
                result.append(b)
            else:
                if b['value'].strip() or '\n' in b['value']:
                    result.append(b)

        print(f"Merged {len(blocks)} blocks into {len(result)} blocks.")
        return result
