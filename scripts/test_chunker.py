from backend.ingestion.chunker import chunk_passage
import sys

text = """
We change this Privacy Policy from time to time. We will not reduce your rights under this
Privacy Policy without your explicit consent. We always indicate the date the last
changes were published and we offer access to archived versions for your review. If
changes are significant, we’ll provide a more prominent notice (including, for certain
services, email notification of Privacy Policy changes).

RELATED PRIVACY PRACTICES
"""

chunks = chunk_passage(text, passage_id="test", title="test", source_doc="test")
for c in chunks:
    print("---")
    print(c.text)
