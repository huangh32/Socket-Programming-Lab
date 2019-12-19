#!/usr/bin/python3

"""
Echo Client and Server Classes

T. D. Todd
McMaster University

to create a Client: "python EchoClientServer.py -r client"
to create a Server: "python EchoClientServer.py -r server"

or you can import the module into another file, e.g.,
import EchoClientServer

"""

########################################################################

import socket
import argparse
import sys
import threading
import os
import time

########################################################################
# Util functions
########################################################################

def safe_receive(tcp_socket, buffer_size):
    try:
        # Receive and print out text. The received bytes objects
        # must be decoded into string objects.
        recvd_bytes = tcp_socket.recv(buffer_size)
        return recvd_bytes
    except Exception as msg:
        print('safe_receive')
        print(msg)
        sys.exit(1)


def send_file_TCP(tcp_socket, buffer_size, encoding, path, file_name):
    file_path = path + "/" + file_name

    # send the file name
    tcp_socket.sendall(file_name.encode(encoding))
    safe_receive(tcp_socket, buffer_size)

    # send the file size
    bytes_remaining = os.path.getsize(file_path)
    tcp_socket.sendall(str(bytes_remaining).encode(encoding))
    safe_receive(tcp_socket, buffer_size)

    print("Sent file: {}  size: {}".format(file_name, bytes_remaining))

    # keep sending until total is sent
    with open(file_path, "rb") as f:
        while bytes_remaining > 0:
            data = f.read(buffer_size)
            bytes_remaining -= len(data)
            tcp_socket.sendall(data)


def receive_file_TCP(tcp_socket, buffer_size, encoding, path):
    # receive file name
    file_name = safe_receive(tcp_socket, buffer_size).decode(encoding)
    tcp_socket.sendall("ok".encode(encoding))
    file_path = path + "/" + file_name

    # receive size of file
    byte_remind = int(safe_receive(tcp_socket, buffer_size).decode(encoding))
    tcp_socket.sendall('ok'.encode(encoding))

    print("Received file: {}  size: {}".format(file_name, byte_remind))

    # keep receiving until total is sent
    buffer="".encode('utf-8')

    with open(file_path, "wb") as f:
        while byte_remind > 0:
            data = safe_receive(tcp_socket, buffer_size)
            byte_remind -= len(data)
            buffer+=data
            #f.write(data)
    f=open(file_path,'wb')
    f.write(buffer)
    f.close()


class Server:
    HOSTNAME = "0.0.0.0"

    PORT = 3000

    RECV_SIZE = 1024
    BACKLOG = 10

    MSG_ENCODING = "utf-8"
    SOCKET_ADDRESS = (HOSTNAME, PORT)

    ALL_IF_ADDRESS = "0.0.0.0"
    SERVICE_SCAN_PORT = 30000
    ADDRESS_PORT = (ALL_IF_ADDRESS, SERVICE_SCAN_PORT)

    SCAN_CMD = "SERVICE DISCOVERY"
    SCAN_CMD_ENCODED = SCAN_CMD.encode(MSG_ENCODING)

    MSG = "Joey's File Sharing Service"
    MSG_ENCODED = MSG.encode(MSG_ENCODING)

    FILE_DIR = "server_share"

    def __init__(self):
        self.thread_list = []
        self.create_listen_socket()
        self.create_scan_socket()
        self.process_connections_forever()

    def create_scan_socket(self):
        try:
            self.scan_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.scan_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.scan_socket.bind(self.ADDRESS_PORT)

            print("Listening for service discovery messages on SDP port {}".format(self.SERVICE_SCAN_PORT))
            new_thread = threading.Thread(target=self.receive_forever)
            self.thread_list.append(new_thread)
            print("Starting scan thread: ", new_thread.name)
            new_thread.daemon = True
            new_thread.start()
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def receive_forever(self):
        while True:
            try:
                print(Server.MSG, "listening on port {} ...".format(Server.SERVICE_SCAN_PORT))
                recvd_bytes, address = self.scan_socket.recvfrom(Server.RECV_SIZE)

                print("Received: ", recvd_bytes.decode('utf-8'), " Address:", address)
                if recvd_bytes == Server.SCAN_CMD_ENCODED:
                    self.scan_socket.sendto(Server.MSG_ENCODED, address)

            except KeyboardInterrupt:
                print()
                sys.exit(1)

    def create_listen_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(self.SOCKET_ADDRESS)
            self.socket.listen(Server.BACKLOG)
            print("Listening for file sharing connections on port {}".format(self.PORT))

        except Exception as msg:
            print(msg)
            sys.exit(1)

    def process_connections_forever(self):
        try:
            while True:
                new_client = self.socket.accept()

                # A new client has connected. Create a new thread and
                # have it process the client using the connection
                # handler function.
                new_thread = threading.Thread(target=self.connection_handler,
                                              args=(new_client, len(self.thread_list )))

                # Record the new thread.
                self.thread_list.append(new_thread)

                # Start the new thread running.
                print("Starting serving thread: ", new_thread.name)
                new_thread.daemon = True
                new_thread.start()

        except Exception as msg:
            print(msg)
        except KeyboardInterrupt:
            print()
        finally:
            print("Closing server socket ...")
            self.socket.close()
            self.scan_socket.close()
            sys.exit(1)

    def connection_handler(self, client, thread_number):
        connection, address_port = client
        print("-" * 72)
        print("Connection received from {}.".format(address_port))

        while True:
            recvd_bytes = connection.recv(Server.RECV_SIZE)
            if len(recvd_bytes) == 0:
                print("Closing {} client connection ... ".format(address_port))
                connection.close()
                break
            recvd_str = recvd_bytes.decode(Server.MSG_ENCODING)
            print("Received: ", recvd_str)
            if "rlist" in recvd_str:
                response = str(os.listdir(Server.FILE_DIR))
                connection.sendall(response.encode(Server.MSG_ENCODING))
            elif "put" in recvd_str:
                connection.sendall("ok".encode(Server.MSG_ENCODING))
                receive_file_TCP(connection, Server.RECV_SIZE, Server.MSG_ENCODING, Server.FILE_DIR)
            elif "get" in recvd_str:
                _, file_name = recvd_str.split()
                send_file_TCP(connection, Server.RECV_SIZE, Server.MSG_ENCODING, Server.FILE_DIR, file_name)
            elif "bye" in recvd_str:
                print("Closing {} client connection ... ".format(address_port))
                connection.close()
                break

class Client:
    SERVER_HOSTNAME ="192.168.2.116"

    RECV_SIZE = 1024
    BACKLOG = 10

    MSG_ENCODING = "utf-8"

    FILE_DIR = "client_share"
    BROADCAST_ADDRESS = "192.168.2.116"
    BROADCAST_PORT = 30000
    ADDRESS_PORT = (BROADCAST_ADDRESS, BROADCAST_PORT)

    SCAN_CYCLES = 5
    SCAN_TIMEOUT = 5
    SCAN_INTERVAL = 2

    MESSAGE = "SERVICE DISCOVERY"
    MESSAGE_ENCODED = MESSAGE.encode(MSG_ENCODING)

    def __init__(self):
        self.get_socket()
        self.get_scan_socket()
        self.send_console_input_forever()

    def get_scan_socket(self):
        try:
            self.scan_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.scan_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.scan_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.scan_socket.settimeout(Client.SCAN_TIMEOUT)
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def send_broadcasts_forever(self):
        scan_results = []

        for i in range(Client.SCAN_CYCLES):
            print("Sending broadcast scan {}".format(i))
            while True:
                self.scan_socket.sendto(Client.MESSAGE_ENCODED, Client.ADDRESS_PORT)
                try:
                    recvd_bytes, address = self.scan_socket.recvfrom(Client.RECV_SIZE)
                    recvd_msg = recvd_bytes.decode(Client.MSG_ENCODING)
                    break
                except socket.timeout:
                    print("No Service Found ...")

            if (recvd_msg, address) not in scan_results:
                scan_results.append((recvd_msg, address))

        if scan_results:
            for s in scan_results:
                print(s)

    def get_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def connect_to_server(self):
        try:
            self.socket.connect((Client.SERVER_HOSTNAME, Server.PORT))
            print('Connected')
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def get_console_input(self):
        # In this version we keep prompting the user until a non-blank
        # line is entered.
        while True:
            self.input_text = input("Input: ")
            if self.input_text != "":
                break

    def send_console_input_forever(self):
        while True:
            try:
                self.get_console_input()
                self.handle_input()
            except (KeyboardInterrupt, EOFError):
                print()
                print("Closing server connection ...")
                self.socket.close()
                self.scan_socket.close()
                sys.exit(1)

    def handle_input(self):
        encoded_input_text = self.input_text.encode(Client.MSG_ENCODING)

        if "scan" in self.input_text:
            self.send_broadcasts_forever()
        elif "Connect" in self.input_text:
            self.connect_to_server()
        elif "llist" in self.input_text:
            print(os.listdir(Client.FILE_DIR))
        elif "rlist" in self.input_text:
            self.socket.sendall(encoded_input_text)
            response = self.socket.recv(Client.RECV_SIZE).decode(Client.MSG_ENCODING)
            print(response)
        elif "put" in self.input_text:
            _, file_name = self.input_text.split()
            self.socket.sendall(encoded_input_text)
            msg = safe_receive(self.socket, Client.RECV_SIZE).decode(Client.MSG_ENCODING)
            print(msg)
            send_file_TCP(self.socket, Client.RECV_SIZE, Client.MSG_ENCODING, Client.FILE_DIR, file_name)
        elif "get" in self.input_text:
            self.socket.sendall(encoded_input_text)
            receive_file_TCP(self.socket, Client.RECV_SIZE, Client.MSG_ENCODING, Client.FILE_DIR)
        elif "bye" in self.input_text:
            self.socket.sendall(encoded_input_text)
            self.socket.close()
            sys.exit(1)

if __name__ == '__main__':
    roles = {'client': Client,'server': Server}
    parser = argparse.ArgumentParser()

    parser.add_argument('-r', '--role',
                        choices=roles,
                        help='server or client role',
                        required=True, type=str)

    args = parser.parse_args()
    roles[args.role]()

