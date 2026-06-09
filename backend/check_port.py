
import socket

def check_port(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"端口 {port} 是开放的")
            return True
        else:
            print(f"端口 {port} 是关闭的")
            return False
    finally:
        sock.close()

print("检查端口 1824...")
if check_port('127.0.0.1', 1824):
    print()
    print("服务可能已经在运行！")
    print("尝试访问: http://127.0.0.1:1824")
else:
    print()
    print("端口未被占用，可以启动服务")
