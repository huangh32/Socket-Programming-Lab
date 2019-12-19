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
import csv
import getpass
import hashlib
########################################################################
# Echo Server class
########################################################################

class Server:

    # Set the server hostname used to define the server socket address
    # binding. Note that 0.0.0.0 or "" serves as INADDR_ANY. i.e.,
    # bind to all local network interface addresses.
    HOSTNAME = "0.0.0.0"

    # Set the server port to bind the listen socket to.
    PORT = 50000

    RECV_BUFFER_SIZE = 1024
    MAX_CONNECTION_BACKLOG = 10
    
    MSG_ENCODING = "utf-8"

    # Create server socket address. It is a tuple containing
    # address/hostname and port.
    SOCKET_ADDRESS = (HOSTNAME, PORT)

    def __init__(self):
        self.print_file()
        self.create_listen_socket()
        self.process_connections_forever()

    def print_file(self):
        with open('course_grades_2018.csv') as csvfile:
             reader = csv.reader(csvfile, delimiter=',')
             print("Data read from CSV file:")
             for row in reader:
                 print(row)

    def create_listen_socket(self):
        try:
            # Create an IPv4 TCP socket.
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Set socket layer socket options. This allows us to reuse
            # the socket without waiting for any timeouts.
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind socket to socket address, i.e., IP address and port.
            self.socket.bind(Server.SOCKET_ADDRESS)

            # Set socket to listen state.
            self.socket.listen(Server.MAX_CONNECTION_BACKLOG)
            print("Listening on port {} ...".format(Server.PORT))
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def process_connections_forever(self):
        try:
            while True:
                # Block while waiting for accepting incoming
                # connections. When one is accepted, pass the new
                # (cloned) socket reference to the connection handler
                # function.
                self.connection_handler(self.socket.accept())
        except Exception as msg:
            print(msg)
        except KeyboardInterrupt:
            print()

    def connection_handler(self, client):
        connection, address_port = client
        print("-" * 72)
        print("Connection received from {}.".format(address_port))

        while True:
            try:
                # Receive bytes over the TCP connection. This will block
                # until "at least 1 byte or more" is available.
                recvd_bytes = connection.recv(Server.RECV_BUFFER_SIZE)
            
                # If recv returns with zero bytes, the other end of the
                # TCP connection has closed (The other end is probably in
                # FIN WAIT 2 and we are in CLOSE WAIT.). If so, close the
                # server end of the connection and get the next client
                # connection.
                if len(recvd_bytes) == 0:
                    print("Closing client connection ... ")
                    connection.close()
                    break
                
                # Decode the received bytes back into strings. Then output
                # them.
                recvd_str = recvd_bytes.decode(Server.MSG_ENCODING)
                #print("Received: ", recvd_str)

                with open('course_grades_2018.csv') as csvfile:
                    reader = csv.reader(csvfile, delimiter=',')
                    
                    if (recvd_str == 'GAC'):
                        print("Received GAC from client.")
                        string=''
                        for row in reader:
                            if (row[0]=="Averages"):
                               for i in range (0,len(row)):
                                  string+=row[i]
                                  string+=' '                           
                               connection.sendall(string.encode(Server.MSG_ENCODING))
                
                    else:
                        print("Received ID/Password hash:<",recvd_str,">from client.")
                        for row in reader:
                            flag=0
                            string=''
                            m = hashlib.sha256()
                            m.update(row[0].encode(Server.MSG_ENCODING))
                            m.update(row[1].encode(Server.MSG_ENCODING))
                            if m.hexdigest()==recvd_str:
                               
                               #message='Correct Identification'
                               #print(message)
                               #connection.sendall(message.encode(Server.MSG_ENCODING))
                               message2=row
                               #print(message2)
                               #for i in range (2,len(row)):
                                #  print(row[i])
                                 # connection.sendall(row[i].encode(Server.MSG_ENCODING))
                               flag=1
                               break
                        if(flag==1):
               
                            print("Correct Password, record found")
                            for i in range (2,len(message2)):
                                string+=message2[i]
                                string+=' '
                            connection.sendall(string.encode(Server.MSG_ENCODING))
                        else:
                            message='Password Failure, Please re-enter.'
                            print("Error Message Sent: Password Failure")
                            connection.sendall(message.encode(Server.MSG_ENCODING))                            
                            
                
                # Send the received bytes back to the client.
                #connection.sendall(recvd_bytes)
                #print("Sent: ", recvd_str)
                print("Closing client connection ... ")
                connection.close()
                break

            except KeyboardInterrupt:
                print()
                print("Closing client connection ... ")
                connection.close()
                break

########################################################################
# Echo Client class
########################################################################

class Client:

    # Set the server hostname to connect to. If the server and client
    # are running on the same machine, we can use the current
    # hostname.
    SERVER_HOSTNAME = socket.gethostname()

    RECV_BUFFER_SIZE = 1024

    def __init__(self):
        self.get_command()
       

    def get_command(self):
        while True:
            self.input_text = input("Input: ")
            if  self.input_text != 'GAC':
                
                self.input_text=input("Student ID:")
                self.password=getpass.getpass(prompt='Password:')
                #print(self.input_text)
                if (self.input_text=="" or self.input_text==" "):
                    print("Entered invalid, please re-enter")
                    self.get_command()

                print("ID number sent:",self.input_text,", Password sent:",self.password)
                
                self.get_socket()
                self.connect_to_server()
                self.send_console_input_forever()
            else:
                print("Command entered:",self.input_text)
                print("Fetching grade averages:")
                self.get_socket()
                self.connect_to_server()
                self.send_console_input_forever()

    def get_socket(self):
        try:
            # Create an IPv4 TCP socket.
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def connect_to_server(self):
        try:
            # Connect to the server using its socket address tuple.
            self.socket.connect((Client.SERVER_HOSTNAME, Server.PORT))
        except Exception as msg:
            print(msg)
            sys.exit(1)

    def get_console_input(self):
        # In this version we keep prompting the user until a non-blank
        # line is entered.
        while True:
            self.input_text = input("Input: ")
            #print (self.input_text)
            if  self.input_text != '' and self.input_text != 'GAC':
                self.password=getpass.getpass(prompt='password:')
                
    
    def send_console_input_forever(self):
        while True:
            try:
                #self.get_console_input()
                self.connection_send()
                self.connection_receive()
                self.get_command()
            except (KeyboardInterrupt, EOFError):
                print()
                print("Closing server connection ...")
                self.socket.close()
                sys.exit(1)
                
    def connection_send(self):
        try:
            # Send string objects over the connection. The string must
            # be encoded into bytes objects first.
           
            if self.input_text != "GAC" and self.input_text!=" ":
               m = hashlib.sha256()
               m.update(self.input_text.encode(Server.MSG_ENCODING))
               m.update(self.password.encode(Server.MSG_ENCODING))
               self.socket.sendall(m.hexdigest().encode(Server.MSG_ENCODING))
               print("ID/Password hash:<", m.hexdigest(),">sent to server")

            elif self.input_text == "GAC":
               
               self.socket.sendall(self.input_text.encode(Server.MSG_ENCODING))

        except Exception as msg:
            print(msg)
            sys.exit(1)

    def connection_receive(self):
        try:
            # Receive and print out text. The received bytes objects
            # must be decoded into string objects.
            recvd_bytes = self.socket.recv(Client.RECV_BUFFER_SIZE)

            # recv will block if nothing is available. If we receive
            # zero bytes, the connection has been closed from the
            # other end. In that case, close the connection on this
            # end and exit.
            if len(recvd_bytes) == 0:
                print("Closing server connection ... ")
                self.socket.close()
                sys.exit(1)

            print("Received: ", recvd_bytes.decode(Server.MSG_ENCODING))

        except Exception as msg:
            print(msg)
            sys.exit(1)

########################################################################
# Process command line arguments if this module is run directly.
########################################################################

# When the python interpreter runs this module directly (rather than
# importing it into another file) it sets the __name__ variable to a
# value of "__main__". If this file is imported from another module,
# then __name__ will be set to that module's name.

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






