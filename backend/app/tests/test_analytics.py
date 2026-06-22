from backend.app.services.analytics import classify_topic

def test_classify_topic():
    assert classify_topic("what is the data retention policy?") == "Data Retention"
    assert classify_topic("how do you share data with third parties") == "Third-Party Sharing"
    assert classify_topic("how to delete cookies") == "Cookies"
    assert classify_topic("do you sell my info") == "Data Sale / Opt-out"
    assert classify_topic("what is the capital of France") == "Other"
