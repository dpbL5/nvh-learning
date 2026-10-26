import json
import time

from django.core.management.base import BaseCommand

from ai_core.services.ai_generator import (
    GENERATION_CONFIG_JSON_STRICT,
    RAG_GENERATION_MODEL,
    AIGeneratorService,
    ai_client,
)
from exams.models import Question

GRADE_PROMPT = """Bạn phân loại câu hỏi Tin học THPT Việt Nam theo khối lớp.

Chương trình Tin học:
- Lớp 10: máy tính và xã hội tri thức, dữ liệu - thông tin, mạng máy tính, ứng dụng tin học.
- Lớp 11: hệ điều hành, phần mềm ứng dụng, lập trình Python cơ bản, dữ liệu số.
- Lớp 12: cơ sở dữ liệu, hệ quản trị CSDL, mạng và Internet nâng cao, trí tuệ nhân tạo.

Với mỗi câu hỏi dưới đây, chọn đúng MỘT khối lớp ("10", "11" hoặc "12") mà kiến thức của câu thuộc chương trình.
Không mặc định tất cả về lớp 10. Nếu câu hỏi không đủ dữ kiện để xác định chắc chắn, để "grade": "".

Trả về DUY NHẤT một JSON array, không markdown, không giải thích:
[{{"id": <số id>, "grade": "10" | "11" | "12" | ""}}]

DANH SÁCH CÂU HỎI:
{questions}
"""


class Command(BaseCommand):
    help = 'Dùng AI phân loại khối lớp (10/11/12) cho các câu hỏi chưa có grade.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Số câu tối đa cần xử lý (0 = tất cả).')
        parser.add_argument('--batch-size', type=int, default=10, help='Số câu mỗi lần gọi AI.')
        parser.add_argument('--dry-run', action='store_true', help='Chỉ in kết quả, không ghi DB.')
        parser.add_argument('--overwrite', action='store_true', help='Phân loại lại cả câu đã có grade.')
        parser.add_argument('--sleep', type=float, default=0.5, help='Nghỉ giữa các batch (giây).')

    def handle(self, *args, **options):
        if not ai_client.is_configured():
            self.stderr.write(self.style.ERROR('AI API key chưa được cấu hình.'))
            return

        limit = max(0, options['limit'])
        batch_size = max(1, options['batch_size'])
        dry_run = options['dry_run']
        overwrite = options['overwrite']
        sleep_seconds = max(0.0, options['sleep'])

        queryset = Question.objects.all().order_by('pk')
        if not overwrite:
            queryset = queryset.filter(grade='')
        if limit:
            queryset = queryset[:limit]

        questions = list(queryset)
        if not questions:
            self.stdout.write(self.style.WARNING('Không có câu hỏi nào cần phân loại.'))
            return

        updated = 0
        skipped = 0

        for start in range(0, len(questions), batch_size):
            batch = questions[start:start + batch_size]
            payload = [
                {
                    'id': question.pk,
                    'subject': question.subject.name if question.subject_id else '',
                    'topic': question.topic or '',
                    'question_type': question.question_type,
                    'question_text': question.question_text or '',
                    'context': (question.context or '')[:1500],
                    'text': (question.text or '')[:1500],
                    'options': [option.text for option in question.options.all()],
                }
                for question in batch
            ]
            prompt = GRADE_PROMPT.format(
                questions=json.dumps(payload, ensure_ascii=False)
            )

            try:
                response = ai_client.generate_content(
                    prompt,
                    model=RAG_GENERATION_MODEL,
                    config=GENERATION_CONFIG_JSON_STRICT,
                )
                predictions = AIGeneratorService._parse_model_json(response.text)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'Lỗi batch {start}: {exc}'))
                skipped += len(batch)
                continue

            by_id = {}
            for prediction in predictions:
                if not isinstance(prediction, dict):
                    continue
                try:
                    question_id = int(prediction.get('id'))
                except (TypeError, ValueError):
                    continue
                grade = str(prediction.get('grade') or '').strip()
                by_id[question_id] = grade if grade in ('10', '11', '12') else ''

            for question in batch:
                if question.pk not in by_id:
                    skipped += 1
                    continue
                grade = by_id[question.pk]
                if not grade:
                    skipped += 1
                    continue
                self.stdout.write(f'Câu {question.pk}: {question.grade or "(trống)"} -> {grade}')
                if not dry_run:
                    question.grade = grade
                    question.save(update_fields=['grade'])
                updated += 1

            if sleep_seconds and start + batch_size < len(questions):
                time.sleep(sleep_seconds)

        prefix = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Đã phân loại {updated} câu, bỏ qua {skipped} câu.'
        ))
