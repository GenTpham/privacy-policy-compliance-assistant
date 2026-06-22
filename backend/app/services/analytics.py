import re

TOPIC_RULES = [
    (re.compile(r"cookie|tracker|theo dõi", re.IGNORECASE), "Cookies"),
    (re.compile(r"third.?party|bên thứ ba|share|chia sẻ", re.IGNORECASE), "Third-Party Sharing"),
    (re.compile(r"sell|bán|opt.?out", re.IGNORECASE), "Data Sale / Opt-out"),
    (re.compile(r"retention|lưu trữ|xóa|delete", re.IGNORECASE), "Data Retention"),
]

def classify_topic(query: str) -> str:
    for pattern, topic in TOPIC_RULES:
        if pattern.search(query):
            return topic
    return "Other"
