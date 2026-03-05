import os


GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
GEMINI_API_URL = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'

POST_SUMMARY_MIN_CHARS = 500
POST_SUMMARY_MAX_INPUT_CHARS = 8000
POST_SUMMARY_MAX_OUTPUT_TOKENS = 220
POST_SUMMARY_TEMPERATURE = 0.3

POST_SUMMARY_PROMPT = (
    'Ти стисло підсумовуєш текст поста мовою самого тексту. '
    'Зроби 3-5 коротких речень без вигадування фактів, тільки на основі вхідного тексту. '
    'Підсумок має бути строго про тему вхідного тексту; не підміняй тему і не додавай сторонніх фактів. '
    'Якщо у тексті немає згадки про певні поняття, не згадуй їх у підсумку. '
    'Якщо текст неінформативний, поверни максимально короткий нейтральний підсумок.'
    'Не додавай ніяких зайвих відповідей. Тільки підсумовування і нічого більше.'
)