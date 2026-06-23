import sys
sys.path.insert(0, r"D:\data\code\privacy-policy-compliance-assistant")
try:
    import backend.app.main
    print("OK")
except Exception as e:
    import traceback
    traceback.print_exc()
