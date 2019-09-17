# Written by Wenxun Peng for COMP9331 assignment in 27/09/2018 using python 3.6

# A file is to be transferred from the sender to receiver.
# Data segments will flow from the sender to receiver.
# ACK segments will flow from the receiver to sender.
from socket import *
import time
import sys
import struct


# ############################################# Define class and function ##############################################

# Define the STP segment
mss = 0     # initializing the mss


def get_in_bytes(syn=0, ack=0, fin=0, seq=0, acknowledgement=0, length=mss,  checksum=0, data=b''):
    fmt = "!7i%ds" % length
    buf = struct.pack(fmt, syn, ack, fin, seq, acknowledgement, length, checksum, data)
    return buf


def unpack_data(data):  # make data easier to operate
    length = mss
    fmt = "!7i%ds" % length
    message = struct.unpack(fmt, data)
    result = Segments(syn=int(message[0]), ack=int(message[1]), fin=int(message[2]), seq_value=int(message[3]),
                      ack_value=int(message[4]), checksum_value=int(message[6]), checksum_flag=1, data=message[7])
    return result

# the length of checksum is 8 bits, because the the maximum ASCII is 255, which is 11111111


def checksum(data=b''):
    sum_value = 0
    for convert_data_in_nb in data:
        sum_value = sum_value + convert_data_in_nb
        while sum_value >= 256:         # wraparound (the max length is 10 because 0b11111111)
            sum_value = sum_value - 256 + 1
    checksum = 255 - sum_value
    return checksum, sum_value


class Segments:  # Define the STP segment
    def __init__(self, syn=0, ack=0, fin=0, seq_value=0, ack_value=0, checksum_value=0, checksum_flag=0, data=b''):
        self.SYN_Flag, self.ACK_Flag, self.FIN_Flag = syn, ack, fin    # ack flag
        self.ACK_Value = ack_value  # ack value
        self.SEQ_Value = seq_value  # sequence number
        self.DATA = data
        if checksum_flag == 0:
            checksum_value, sum_value = checksum(data=data)     # sum_value is for checking error bit
            self.sum_value = sum_value
        self.checksum = checksum_value
        self.segment = get_in_bytes(syn=syn, ack=ack, fin=fin, seq=seq_value, acknowledgement=ack_value, length=mss,
                                    checksum=checksum_value, data=data)  # segment in bit


# ########################################## Preparing something to use and count ######################################
# Create a UDP socket
try:
    receiverSocket = socket(AF_INET, SOCK_DGRAM)
except:
    print("Failed to create receiver socket.")
    sys.exit()

# Bind socket to host and port
receiverPort = int(sys.argv[1])
# receiverPort = 3300
try:
    receiverSocket.bind(('', receiverPort))
except:
    print("Bind failed.")
    sys.exit()

print("Waiting for connecting...")
# Create a Reiceiver_log file
receiver_log = open("Receiver_log.txt", "w")

# Define some useful data to be recorded
amount_of_data = 0  # Amount of Data Received (in bytes) including retransmitted data
nb_of_total_segment = 0  # Total segments received
nb_of_data_segment = 0  # Data segments received
nb_of_corrupt = 0  # Data Segments with bit errors
nb_of_duplicate = 0  # Duplicate data segments received
nb_of_DA_sent = 0  # Duplicate Acks sent


# ############################################ A three-way handshake  ##################################################

receiver_seq = 99  # initialising the sequence number of receiver
start_time = time.time()

# first hand
first_hand, senderAddress = receiverSocket.recvfrom(2048)
mss = len(first_hand) - 28  # calculating the length of mss
first_hand_unpack = unpack_data(first_hand)
curr_time = time.time()
time_to_log = curr_time - start_time
receiver_log.writelines(
    "rcv  {:.3f}  S {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, first_hand_unpack.SEQ_Value, len(first_hand_unpack.DATA),
                                                first_hand_unpack.ACK_Value))
nb_of_total_segment += 1

# second hand
if first_hand_unpack.SYN_Flag == 1:
    print("First handshake receiving SYN...")
    second_hand = Segments(seq_value=receiver_seq, ack=1, ack_value=first_hand_unpack.SEQ_Value + 1, syn=1)
    receiverSocket.sendto(second_hand.segment, senderAddress)
    curr_time = time.time()
    time_to_log = curr_time - start_time
    receiver_log.writelines(
        "snd  {:.3f}  SA{:5d} {:3d} {:5d}\n".format(time_to_log * 1000, second_hand.SEQ_Value, len(second_hand.DATA),
                                                    second_hand.ACK_Value))
    print("Second handshake sending SYNACK...")
else:
    print("Connection error!!!")
    receiverSocket.close()

# third hand
third_hand, senderAddress = receiverSocket.recvfrom(2048)
third_hand_unpack = unpack_data(third_hand)
curr_time = time.time()
time_to_log = curr_time - start_time
receiver_log.writelines(
    "rcv  {:.3f}  S {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, third_hand_unpack.SEQ_Value, len(third_hand_unpack.DATA),
                                                third_hand_unpack.ACK_Value))
nb_of_total_segment += 1
if third_hand_unpack.ACK_Flag == 1:
    print("Third handshake receiving ACK...")
    print("Connecting...")
    print("Waiting for data...")
else:
    print("Connection error!!")
    receiverSocket.close()
    sys.exit()

# ############################# Receiving data and putting it into a new file ##########################################

# creating a new file to write in
file_name = sys.argv[2]
# file_name = 'file_r.pdf'
f = open(file_name, "wb")

# waiting for the first segments
message, senderAddress = receiverSocket.recvfrom(2048)
message_unpack = unpack_data(message)
nb_of_total_segment += 1
amount_of_data += len(message_unpack.DATA)

# initializing some useful data
seq_num = third_hand_unpack.ACK_Value  # initialising the seq number of receiver
expected_seq = third_hand_unpack.SEQ_Value  # the sequence number we needed next (correct order)
already_seq = []  # judging whether sending duplicated ack or not
last_seq = []  # the sequence number that has been received
waiting_list = []  # an empty list to buffer the segments out of order

# update the file while the fin flag is 0
while message_unpack.FIN_Flag == 0:

    # if the seq number is in correct order
    # print(f'seq_value is {message_unpack.SEQ_Value} and expected_seq is {expected_seq}')
    if message_unpack.SEQ_Value == expected_seq:

        # judging whether the data is correct, we using the checksum is 8 bits, so if it is correct,
        # the result should be 255(0b11111111)
        corrupt_checksum, corrupt_sum_value = checksum(message_unpack.DATA)

        if (message_unpack.checksum + corrupt_sum_value) == 255:     # no bit error
            # print(message_unpack.checksum)
            f.write(message_unpack.DATA)
            expected_seq += len(message_unpack.DATA)
            last_seq.append(message_unpack.SEQ_Value)

            curr_time = time.time()
            time_to_log = curr_time - start_time
            print("rcv:  seq:{} ack:{}".format(message_unpack.SEQ_Value, message_unpack.ACK_Value))
            receiver_log.writelines(
                "rcv  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, message_unpack.SEQ_Value,
                                                            len(message_unpack.DATA),
                                                            message_unpack.ACK_Value))

            i = 0
            # to check whether there are correct segments already been transferred
            # print(f'waiting_list is {waiting_list}')
            while i < len(waiting_list):
                # print(f'waiting list has f{waiting_list[i].SEQ_Value}')
                if waiting_list[i].SEQ_Value == expected_seq:
                    f.write(waiting_list[i].DATA)
                    expected_seq += len(waiting_list[i].DATA)
                    del waiting_list[i]
                    i = i - 1
                i += 1
        else:              # data is corrupted so we should require re-transmitting.
            curr_time = time.time()
            time_to_log = curr_time - start_time
            print("rcv/corr:  seq:{} ack:{}".format(message_unpack.SEQ_Value, message_unpack.ACK_Value))
            receiver_log.writelines(
                "rcv&corr  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, message_unpack.SEQ_Value,
                                                            len(message_unpack.DATA),
                                                            message_unpack.ACK_Value))
            nb_of_corrupt += 1
    # if the sequence number is not in correct order
    else:

        # judging whether the data is correct, we using the checksum is 8 bits, so if it is correct,
        # the result should be 255(0b11111111)
        corrupt_checksum, corrupt_sum_value = checksum(message_unpack.DATA)

        if (message_unpack.checksum + corrupt_sum_value) == 255:    # no bit error
            # to compute the dup seqement
            # print(message_unpack.checksum)
            if message_unpack.SEQ_Value in last_seq:
                nb_of_duplicate += 1

                curr_time = time.time()
                time_to_log = curr_time - start_time
                print("rcv/dup:  seq:{} ack:{}".format(message_unpack.SEQ_Value, message_unpack.ACK_Value))
                receiver_log.writelines(
                    "rcv&dup  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, message_unpack.SEQ_Value,
                                                                len(message_unpack.DATA),
                                                                message_unpack.ACK_Value))
                nb_of_duplicate += 1
            else:
                last_seq.append(message_unpack.SEQ_Value)
                curr_time = time.time()
                time_to_log = curr_time - start_time
                print("rcv:  seq:{} ack:{}".format(message_unpack.SEQ_Value, message_unpack.ACK_Value))
                receiver_log.writelines(
                    "rcv  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, message_unpack.SEQ_Value,
                                                                len(message_unpack.DATA),
                                                                message_unpack.ACK_Value))
                # if there is no segments in waiting list, just add it in waiting_list (just like a buffer)
                # print(f'wrong order and waiting list is {waiting_list}')
                if not waiting_list:
                    waiting_list.append(message_unpack)
                else:
                    # to insert the new message at a right position in waiting list
                    for i in range(0, len(waiting_list)):
                        if waiting_list[i].SEQ_Value > message_unpack.SEQ_Value:
                            waiting_list.insert(i, message_unpack)
                            break
                        if i == len(waiting_list) - 1:
                            waiting_list.append(message_unpack)
                            break
        else:                                 # bit error
            curr_time = time.time()
            time_to_log = curr_time - start_time
            print("rcv/corr:  seq:{} ack:{}".format(message_unpack.SEQ_Value, message_unpack.ACK_Value))
            receiver_log.writelines(
                "rcv&corr  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, message_unpack.SEQ_Value,
                                                            len(message_unpack.DATA),
                                                            message_unpack.ACK_Value))
            nb_of_corrupt += 1

    # sending the needed seq number in ack value
    if expected_seq in already_seq:
        curr_time = time.time()
        time_to_log = curr_time - start_time
        response = Segments(seq_value=seq_num, ack=1, ack_value=expected_seq)
        receiverSocket.sendto(response.segment, senderAddress)
        print("snd/DA:  seq:{} ack:{}".format(response.SEQ_Value, response.ACK_Value))
        receiver_log.writelines(
            "snd&DA  {:.3f}  A {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, response.SEQ_Value, len(response.DATA),
                                                    response.ACK_Value))
        nb_of_DA_sent += 1
    else:
        response = Segments(seq_value=seq_num, ack=1, ack_value=expected_seq)
        receiverSocket.sendto(response.segment, senderAddress)
        curr_time = time.time()
        time_to_log = curr_time - start_time
        receiver_log.writelines(
            "snd  {:.3f}  A {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, response.SEQ_Value, len(response.DATA),
                                                        response.ACK_Value))
        print("snd:     seq:{} ack:{}".format(response.SEQ_Value, response.ACK_Value))
        already_seq.append(expected_seq)

    # receive segments from sender
    message, senderAddress = receiverSocket.recvfrom(2048)
    message_unpack = unpack_data(message)
    nb_of_total_segment += 1
    nb_of_data_segment += 1
    amount_of_data += len(message_unpack.DATA)
print("File Download...")


# ################################## Four-segment connection termination ###############################################

# receiving the fin flag
first_end = message
first_end_unpack = unpack_data(first_end)
receiverSocket.settimeout(1)
if first_end_unpack.FIN_Flag == 1:
    curr_time = time.time()
    time_to_log = curr_time - start_time
    receiver_log.writelines(
        "rcv  {:.3f}  F {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, first_end_unpack.SEQ_Value, len(first_end_unpack.DATA),
                                                    first_end_unpack.ACK_Value))
    print("Receiving FIN and sending FINACK...")
    nb_of_total_segment += 1

    # send the ack flag
    second_end = Segments(seq_value=first_end_unpack.ACK_Value, ack=1, ack_value=first_end_unpack.SEQ_Value + 1)
    receiverSocket.sendto(second_end.segment, senderAddress)
    curr_time = time.time()
    time_to_log = curr_time - start_time
    receiver_log.writelines(
        "snd  {:.3f}  A{:5d} {:3d} {:5d}\n".format(time_to_log * 1000, second_end.SEQ_Value,
                                                    len(second_end.DATA), second_end.ACK_Value))

    # send the FINACK flag
    third_end = Segments(seq_value=first_end_unpack.ACK_Value, ack_value=first_end_unpack.SEQ_Value + 1, fin=1)
    receiverSocket.sendto(third_end.segment, senderAddress)
    curr_time = time.time()
    time_to_log = curr_time - start_time
    receiver_log.writelines(
        "snd  {:.3f}  FA{:5d} {:3d} {:5d}\n".format(time_to_log * 1000, third_end.SEQ_Value, len(third_end.DATA),
                                                    third_end.ACK_Value))

    print("Sending ACK and FINACK...")

# receive the ack flag, then shut down
try:
    forth_end, senderAddress = receiverSocket.recvfrom(2048)
    forth_end_unpack = unpack_data(forth_end)
    curr_time = time.time()
    time_to_log = curr_time - start_time
    receiver_log.writelines(
        "rcv  {:.3f}  A {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, forth_end_unpack.SEQ_Value, len(forth_end_unpack.DATA),
                                                    forth_end_unpack.ACK_Value))
    nb_of_total_segment += 1
    if forth_end_unpack.ACK_Flag == 1:
        receiverSocket.close()
        print("close receiver")
except timeout:
    curr_time = time.time()
    time_to_log = curr_time - start_time
    receiver_log.writelines("rcv  {:.3f}  A {:5d} {:3d} {:5d}\n".format(time_to_log * 1000, first_end_unpack.SEQ_Value + 1, 0,
                                                                        first_end_unpack.ACK_Value + 1))
    receiverSocket.close()
    print("close receiver")

# f.seek(0, 2)
receiver_log.writelines("Amount of Data Received (bytes): %d\n" % amount_of_data)
receiver_log.writelines("Total segments received: %d\n" % nb_of_total_segment)
receiver_log.writelines("Data segments received: %d\n" % nb_of_data_segment)
receiver_log.writelines("Data Segments with bit errors: %d\n" % nb_of_corrupt)
receiver_log.writelines("Duplicate data segments received: %d\n" % nb_of_duplicate)
receiver_log.writelines("Duplicate Acks sent: %d\n" % nb_of_DA_sent)
f.close()
receiver_log.close()
