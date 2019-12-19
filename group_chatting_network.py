#!/usr/bin/env python3

########################################################################

import socket
import argparse
import sys
import select
import queue
import re
import json
import threading
import struct
import time

########################################################################
# SERVER
########################################################################

class Server:

    HOSTNAME = "0.0.0.0"
    CRDP = 50000

    BACKLOG = 5
    RECV_SIZE = 1024

    MSG_ENCODING = "utf-8"

    CRD_ENTRY_LIST = []

    def __init__(self):
        self.create_listen_socket()
        self.initialize_select_lists()
        self.process_connections_forever()

    def initialize_select_lists(self):
        self.read_list = [self.listen_socket]
        self.write_list = []

    def create_listen_socket(self):
        try:
            self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listen_socket.bind((Server.HOSTNAME, Server.CRDP))
            self.listen_socket.listen(Server.BACKLOG)
            print("Chat Room Directory Server listening on port {} ...".format(Server.CRDP))
        except Exception as msg:
            print(msg)
            exit()

    def process_connections_forever(self):
        self.message_queues = {}
        self.chat_rooms_queues = {}

        try:
            while True:
                self.read_ready, self.write_ready, self.except_ready = select.select(
                    self.read_list, self.write_list, [])
                self.process_read_sockets()
                self.process_write_sockets()
        except Exception as msg:
            print(msg)
        except KeyboardInterrupt:
            print()
        finally:
            self.listen_socket.close()

    def process_read_sockets(self):
        for read_socket in self.read_ready:
            if read_socket is self.listen_socket:
                client, address = read_socket.accept()
                print("-" * 72)
                print("Connection received from {}.".format(address))
                client.setblocking(False)
                self.read_list.append(client)
                self.message_queues[client] = queue.Queue()
                connection_msg = b'You are now successfully connected to CRDS'
                self.message_queues[client].put(connection_msg)
                self.write_list.append(client)

            else:
                recv_bytes = read_socket.recv(Server.RECV_SIZE)

                if len(recv_bytes):
                    if "create" in recv_bytes.decode(Server.MSG_ENCODING):
                        m = re.search(r'^create\s(.+)\s(([0-9]+\.){3}[0-9]+)\s([0-9]+)$', recv_bytes.decode(Server.MSG_ENCODING))
                        chat_room_name = m.group(1)
                        multicast_addr_port = (m.group(2), int(m.group(4)))
                        CRD_ENTRY = {"Chat Room Name" : chat_room_name, "Multicast IP Address and Port" : multicast_addr_port}
                        DUPLICATE = False
                        for entry in self.CRD_ENTRY_LIST:
                            if entry["Chat Room Name"] == chat_room_name:
                                self.message_queues[read_socket].put(
                                    b'The requested chat room name has already been used, please choose another name!')
                                DUPLICATE = True
                                break
                            if entry["Multicast IP Address and Port"] == multicast_addr_port:
                                self.message_queues[read_socket].put(b'The requested multicast IP address and port has already been used, please choose another combination!')
                                DUPLICATE = True
                                break
                        if not DUPLICATE:
                            self.CRD_ENTRY_LIST.append(CRD_ENTRY)
                            self.chat_rooms_queues[multicast_addr_port] = queue.Queue()
                            try:
                                chat_room_thread = threading.Thread(target=self.chat_room_handler, args=(multicast_addr_port,))
                                chat_room_thread.setDaemon(True)
                                chat_room_thread.start()

                            except Exception as msg:
                                print(msg)
                                exit(1)
                            except KeyboardInterrupt:
                                print("Quit!")
                                sys.exit(1)

                            self.message_queues[read_socket].put(b'The requested chat room has been successfully created')

                    elif "list" == recv_bytes.decode(Server.MSG_ENCODING):
                        if not self.CRD_ENTRY_LIST:
                            self.message_queues[read_socket].put(b'No chat room has been created')
                        else:
                            serialized_CDR = json.dumps(self.CRD_ENTRY_LIST)
                            serialized_CDR_encoded = serialized_CDR.encode(Server.MSG_ENCODING)
                            self.message_queues[read_socket].put(serialized_CDR_encoded)
                    elif "delete" in recv_bytes.decode(Server.MSG_ENCODING):
                        m = re.search(r'^delete\s(.*)$', recv_bytes.decode(Server.MSG_ENCODING))
                        chat_room_name = m.group(1)
                        isDeleted = False
                        for entry in self.CRD_ENTRY_LIST:
                            if entry["Chat Room Name"] == chat_room_name:
                                self.CRD_ENTRY_LIST.remove(entry)
                                isDeleted = True
                                break

                        if not isDeleted:
                            self.message_queues[read_socket].put(b'The requested chat room does not exist!')
                        else:
                            self.message_queues[read_socket].put(b'The requested chat room has been successfully removed')
                    elif "chat" in recv_bytes.decode(Server.MSG_ENCODING):
                        m = re.search(r'^chat\s(.*)$', recv_bytes.decode(Server.MSG_ENCODING))
                        chat_room_name = m.group(1)
                        doesExist = False
                        for entry in self.CRD_ENTRY_LIST:
                            if entry["Chat Room Name"] == chat_room_name:
                                serialized_ENTRY = json.dumps(entry)
                                serialized_ENTRY_encoded = serialized_ENTRY.encode(Server.MSG_ENCODING)
                                self.message_queues[read_socket].put(serialized_ENTRY_encoded)
                                doesExist = True
                                break
                        if not doesExist:
                            self.message_queues[read_socket].put(b'The requested chat room does not exist!')

                    elif "replay" in recv_bytes.decode(Server.MSG_ENCODING):
                        m = re.search(r'^replay\s(.*)$', recv_bytes.decode(Server.MSG_ENCODING))
                        chat_room_name = m.group(1)
                        doesExist = False
                        for entry in self.CRD_ENTRY_LIST:
                            if entry["Chat Room Name"] == chat_room_name:
                                activity = self.chat_rooms_queues[entry["Multicast IP Address and Port"]]
                                record = ""
                                for element in list(activity.queue):
                                    record += '\n' + element.decode(Server.MSG_ENCODING)
                                if record == "":
                                    record = "No activity"
                                self.message_queues[read_socket].put(record.encode(Server.MSG_ENCODING))
                                doesExist = True
                                break
                        if not doesExist:
                            self.message_queues[read_socket].put(b'The requested chat room does not exist!')

                    if read_socket not in self.write_list:
                        # print("Adding read_socket to write_list: ", read_socket)
                        self.write_list.append(read_socket)
                else:
                    print("Closing client connection ... ")
                    # print("Deleting message queue ...")
                    del self.message_queues[read_socket]
                    self.read_list.remove(read_socket)
                    read_socket.close()


    def process_write_sockets(self):
        for write_socket in self.write_ready:
            try:
                next_msg = self.message_queues[write_socket].get_nowait()
                # print("sending msg = ", next_msg)
                write_socket.sendall(next_msg)
            except (KeyError, queue.Empty) as msg:
                # print(msg)
                # print("Removing socket from write_list: ", write_socket)
                self.write_list.remove(write_socket)

    def chat_room_handler(self, multicast_addr_port):
        multicast_addr, multicast_port = multicast_addr_port
        try:
            receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            receiver_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            receiver_socket.bind(("0.0.0.0", multicast_port))
            multicast_group_bytes = socket.inet_aton(multicast_addr)
            multicast_if_bytes = socket.inet_aton("0.0.0.0")
            multicast_request = multicast_group_bytes + multicast_if_bytes
            receiver_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, multicast_request)
            while True:
                data, address = receiver_socket.recvfrom(256)
                if '\x1d' in data.decode(Server.MSG_ENCODING):
                    msg = data.decode(Server.MSG_ENCODING)
                    m = re.search(r'^(.*):\s.*$', msg)
                    if m:
                        print(m.group(1), "is leaving the chat room!")
                else:
                    print(data.decode(Server.MSG_ENCODING))
                    self.chat_rooms_queues[multicast_addr_port].put(data)

        except KeyboardInterrupt:
            print();
            exit()
        except Exception as msg:
            print(msg)
            sys.exit(1)


########################################################################
# CLIENT
########################################################################

class Client:

    CRDS_HOSTNAME = "192.168.2.26"
    CRDP = 50000
    RECV_SIZE = 1024

    def __init__(self):
        self.send_console_input_forever()

    def get_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def connect_to_server(self):
        try:
            self.socket.connect((Client.CRDS_HOSTNAME, Client.CRDP))
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def get_console_input_before_connection(self):
        while True:
            self.cmd = input("Enter 'connect' to connect to CRDS: ")
            if self.cmd != '':
                break
    def get_console_input_after_connection(self):
        while True:
            self.cmd = input("Enter CRDS cmd: ")
            if self.cmd != '':
                break
    def get_chat_input(self):
        while True:
            self.chat = input()
            if self.chat != '':
                break

    def send_console_input_forever(self):
        while True:
            try:
                self.get_console_input_before_connection()
                if self.cmd == "connect":
                    self.get_socket()
                    self.connect_to_server()
                    self.connection_receive()

                    while True:
                        self.get_console_input_after_connection()
                        if self.cmd == "bye":
                            print("Closing server connection ...")
                            self.socket.close()
                            break
                        elif "name" in self.cmd:
                            m = re.search(r'^name\s(.*)$', self.cmd)
                            if m.group(1):
                                self.NAME = m.group(1)
                                print("Your chat room ID will be", m.group(1))
                            else:
                                print("Invalid input for name setting!")
                        elif "create" in self.cmd:
                            m = re.search(r'^create\s(.+)\s(([0-9]+\.){3}[0-9]+)\s([0-9]+)$', self.cmd)
                            if m:
                                self.connection_send()
                                self.connection_receive()
                            else:
                                print("Wrong format for create cmd!")
                        elif "list" == self.cmd:
                            self.connection_send()
                            self.connection_receive_json()

                        elif "delete" in self.cmd:
                            m = re.search(r'^delete\s(.*)$', self.cmd)
                            if m:
                                self.connection_send()
                                self.connection_receive()
                            else:
                                print("Wrong format for delete cmd!")

                        elif "chat" in self.cmd:
                            m = re.search(r'^chat\s(.*)$', self.cmd)
                            if m:
                                self.connection_send()
                                self.connection_receive_json()
                                multicast_addr_port = self.json_object['Multicast IP Address and Port']
                                self.send_thread = threading.Thread(target=self.chat_mode_send, args=(multicast_addr_port,))
                                self.send_thread.setDaemon(True)
                                self.receive_thread = threading.Thread(target=self.chat_mode_receive, args=(multicast_addr_port,))
                                self.receive_thread.setDaemon(True)
                                self.send_thread.start()
                                self.stop_receiving = False
                                self.receive_thread.start()
                                self.send_thread.join()
                                self.stop_receiving = True
                                self.receive_thread.join()
                            else:
                                print("Wrong format for chat cmd!")
                        elif "replay" in self.cmd:
                            m = re.search(r'^replay\s(.*)$', self.cmd)
                            if m:
                                self.connection_send()
                                print("#"*10, "Chat room activities", "#"*10)
                                self.connection_receive()
                                print("#"*10, "The end", "#"*10)
                            else:
                                print("Wrong format for replay cmd!")

                        else:
                            print("Cmd not recognized by the system, please try again!")

            except (KeyboardInterrupt, EOFError):
                print()
                print("Closing server connection ...")
                self.socket.close()
                sys.exit(1)

    def connection_send(self):
        try:
            self.socket.sendall(self.cmd.encode(Server.MSG_ENCODING))
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def connection_receive(self):
        try:
            recvd_bytes = self.socket.recv(Client.RECV_SIZE)
            if len(recvd_bytes) == 0:
                print("Closing server connection ... ")
                self.socket.close()
                sys.exit(1)
            self.received_msg = recvd_bytes.decode(Server.MSG_ENCODING)
            print("Received: ", self.received_msg)

        except Exception as msg:
            print(msg)
            sys.exit(1)

    def connection_receive_json(self):
        try:
            recvd_bytes = self.socket.recv(Client.RECV_SIZE)
            recvd_bytes_decoded = recvd_bytes.decode(Server.MSG_ENCODING)
            if "No chat room" in recvd_bytes_decoded:
                print("Received: ", recvd_bytes_decoded)
            elif "does not exist" in recvd_bytes_decoded:
                print("Received: ", recvd_bytes_decoded)
            else:
                self.json_object = json.loads(recvd_bytes_decoded)
                if len(recvd_bytes) == 0:
                    print("Closing server connection ... ")
                    self.socket.close()
                    sys.exit(1)
                print("Received: ", self.json_object)


        except Exception as msg:
            print(msg)
            sys.exit(1)

    def chat_mode_send(self, multicast_addr_port):
        multicast_addr, multicast_port = multicast_addr_port
        try:
            sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sender_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('B', 1))
            print("########## Entering chat room ##########")
            while True:
                self.get_chat_input()
                sender_socket.sendto((self.NAME + ": " + self.chat).encode(Server.MSG_ENCODING), (multicast_addr, multicast_port))
                if self.chat[0] == '\x1d':
                    break
            print("########## Leaving chat room ##########")

        except Exception as msg:
            print(msg)
            sys.exit(1)
        except KeyboardInterrupt:
            print()

    def chat_mode_receive(self, multicast_addr_port):
        multicast_addr, multicast_port = multicast_addr_port
        try:
            receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            receiver_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            receiver_socket.bind(("0.0.0.0", multicast_port))
            multicast_group_bytes = socket.inet_aton(multicast_addr)
            multicast_if_bytes = socket.inet_aton("0.0.0.0")
            multicast_request = multicast_group_bytes + multicast_if_bytes
            receiver_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, multicast_request)
            while True:
                data, address = receiver_socket.recvfrom(256)

                if '\x1d' in data.decode(Server.MSG_ENCODING):
                    print("Stop receiving messages from the chat room!")
                    break
                else:
                    print(data.decode(Server.MSG_ENCODING))



        except KeyboardInterrupt:
            print();
            exit()
        except Exception as msg:
            print(msg)
            sys.exit(1)


########################################################################

if __name__ == '__main__':
    roles = {'client': Client,'server': Server}
    parser = argparse.ArgumentParser()

    parser.add_argument('-r', '--role',
                        choices=roles,
                        help='server or client role',
                        required=True, type=str)

    args = parser.parse_args()
    roles[args.role]()

########################################################################





