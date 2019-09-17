import socket
import sys
from multiprocessing import Process


def handle_client(client_socket):
    """handle client connection request"""
    request_data = client_socket.recv(1024)
    print(request_data)
    request_lines = request_data.splitlines()
    for line in request_lines:
        print(line)
    # 'GET /filename HTTP/1.1'
    if len(request_lines[0]):
        request_start_line = request_lines[0].decode("utf-8")

    # get filename, GET /index.html HTTP/1.1
    get_file_name = str(request_start_line).split(' ')
    if get_file_name[0] != "GET":
        print("Incorrect request!")
        return
    else:
        file_name = get_file_name[1][1:]


# open file and read
        try:
            file = open(file_name, "rb")
        except IOError:
            response_start_line = "HTTP/1.1 404 Not Found\r\n"
            response_heads = "Server: My python server\r\n"
            response_body = "The file not found!"
            response = response_start_line + response_heads + "\r\n" + response_body
            client_socket.sendall(bytes(response))
        else:
            file_data = file.read()
            file.close()

            response_start_line = "HTTP/1.1 200 OK\r\n"
            response_heads = "Server: My python server\r\n"
            if file_name.find('.html') > 0:                # html or png
                print(file_name.find('.html'))
                response_content_type = "Content-Type:text/html\r\n"
                response_body = file_data.decode("utf-8")
                response = response_start_line + response_heads + response_content_type + "\r\n" + response_body
                client_socket.sendall(bytes(response))   # in python2
                # client_socket.sendall(bytes(response, "utf-8"))   # in python3
            else:
                response_content_type = "Content-Type:image/png\r\n"
                response_body = file_data
                response = response_start_line + response_heads + response_content_type + "\r\n"
                client_socket.sendall(bytes(response))
                client_socket.sendall(response_body)
        client_socket.close()


if __name__ == "__main__":
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # tcp socket
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # host = socket.gethostname()  # get localhost
    if len(sys.argv) == 2:
        port = int(sys.argv[1])
    else:
        port = 80
    s.bind(("", port))  # 127.0.0.1 port
    s.listen(5)

    while True:
        c, addr = s.accept()  # accept from client
        handle_client_process = Process(target=handle_client, args=(c,))  # build function
        handle_client_process.start()
        c.close()

