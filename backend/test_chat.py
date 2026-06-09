"""测试 /api/chat 接口"""
import httpx
import json
import asyncio

async def test():
    url = "http://127.0.0.1:1824/api/chat"
    payload = {
        "messages": [{"role": "user", "content": "你好，请回复测试成功四个字"}],
        "stream": False
    }
    print(f"[TEST] 发送请求到 {url}...")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            print(f"[TEST] HTTP Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("response", "")
                print(f"[TEST] 回复内容 (前500字): {reply[:500]}")
                
                # 检查是否是模拟回复
                is_mock = "模拟" in reply or "mock" in reply.lower() or "模拟模式" in reply or "模拟回复" in reply
                
                result = {
                    "status": resp.status_code,
                    "is_mock": is_mock,
                    "reply_preview": reply[:500],
                    "reply_length": len(reply),
                    "session_id": data.get("session_id", ""),
                    "has_sources": bool(data.get("sources")),
                    "has_validation": bool(data.get("law_validation_report")),
                }
                with open(r"c:\Users\Administrator\Desktop\jingtou-digital-legal\backend\chat_test_result.json", "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"[TEST] 结果已保存到 chat_test_result.json")
                print(f"[TEST] 是否模拟模式: {is_mock}")
            else:
                print(f"[TEST] 错误响应: {resp.text[:500]}")
                with open(r"c:\Users\Administrator\Desktop\jingtou-digital-legal\backend\chat_test_result.json", "w", encoding="utf-8") as f:
                    json.dump({"status": resp.status_code, "error": resp.text[:500]}, f, ensure_ascii=False)
    except httpx.TimeoutException:
        print("[TEST] 请求超时！")
        with open(r"c:\Users\Administrator\Desktop\jingtou-digital-legal\backend\chat_test_result.json", "w", encoding="utf-8") as f:
            json.dump({"error": "timeout"}, f)
    except Exception as e:
        print(f"[TEST] 异常: {type(e).__name__}: {e}")
        with open(r"c:\Users\Administrator\Desktop\jingtou-digital-legal\backend\chat_test_result.json", "w", encoding="utf-8") as f:
            json.dump({"error": str(e)}, f)

asyncio.run(test())