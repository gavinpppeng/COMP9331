# Written by Wenxun Peng for COMP9331 assignment in 27/09/2018 using python 3.6

# A file is to be transferred from the sender to receiver.
# Data segments will flow from the sender to receiver.
# ACK segments will flow from the receiver to sender.
from socket import *
from random import *
import threading
import time
import sys
import os
import struct


# ############################################ Define class and function ###############################################

# Define the input value
# pDrop = 0.1
pDrop = float(sys.argv[7])
# pDuplicate = 0.1
pDuplicate = float(sys.argv[8])
# pCorrupt = 0.1
pCorrupt = float(sys.argv[9])
# pOrder = 0.1
pOrder = float(sys.argv[10])
# maxOrder = 4
maxOrder = int(sys.argv[11])
nb_waitting_seg = maxOrder
# pDelay = 0
pDelay = float(sys.argv[12])
# maxDelay = 0
maxDelay = float(sys.argv[13])

# Getting receiver host and port
receiverHost = sys.argv[1]
# receiverHost = '127.0.0.1'
receiverPort = int(sys.argv[2])
# receiverPort = 3300

mws = int(sys.argv[4])
# mws = 500
mss = int(sys.argv[5])
# mss = 150
gamma = int(sys.argv[6])
# gamma = 4
seed_num = int(sys.argv[14])
# seed_num = 300
seed(seed_num)

# Define corrupted_bit(data) to make 1 bit error.


def corrupted_bit(data):                               # using this to corrupted a bit and then sending to the receiver
    data_in_bit = data[0]                                # random corrupting 1 bit
    data_in_bit = data_in_bit - 1
    if 0 <= data_in_bit <= 255:             # no need, but some data in test2.pdf can't be packed by struct.packs
        corrupted_bit_in_data = struct.pack('B', data_in_bit)   # because the data in byte is larger than 255
        new_data = corrupted_bit_in_data + data[1:]
        return new_data
    else:
        return data

# Define the STP segment and for sending data, using get_in_byte() to change the segments in bytes.


def get_in_bytes(syn=0, ack=0, fin=0, seq=0, acknowledgement=0, length=mss,  checksum=0, data=b''):
    fmt = "!7i%ds" % length
    buf = struct.pack(fmt, syn, ack, fin, seq, acknowledgement, length, checksum, data)
    return buf


def unpack_data(data):  # unpack data from receiving process and make data easier to operate
    length = mss
    fmt = "!7i%ds" % length
    message = struct.unpack(fmt, data)
    result = Segments(syn=int(message[0]), ack=int(message[1]), fin=int(message[2]),
                      seq_value=int(message[3]), ack_value=int(message[4]), data=message[7])
    return result

# we set 8 bits for the length of checksum, because the the maximum ASCII is 255, which is 11111111


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
        # Checksum_flag is used to determine whether the value of checksum is calculated by checksum ()
        # or by external input, which will be used in the corrupted data section.
        if checksum_flag == 0:
            checksum_value, sum_value = checksum(data=data)     # sum_value is for checking error bit
            self.sum_value = sum_value
        self.checksum = checksum_value
        self.segment = get_in_bytes(syn=syn, ack=ack, fin=fin, seq=seq_value, acknowledgement=ack_value, length=mss,
                                    checksum=checksum_value, data=data)  # segment in bytes


def timeout_value(SampleRTT, initial=True):         # milliseconds
    a = 0.125
    b = 0.25
    global EstimatedRTT
    global DevRTT
    global gamma
    if initial:
        DevRTT = 250
        EstimatedRTT = (1 - a) * 500 + a * SampleRTT
        TimeoutInterval = EstimatedRTT + gamma * DevRTT
        return TimeoutInterval
    else:
        EstimatedRTT = (1-a) * EstimatedRTT + a * SampleRTT
        DevRTT = (1-b) * DevRTT + b * abs(SampleRTT - EstimatedRTT)
        TimeoutInterval = EstimatedRTT + gamma * DevRTT
        return TimeoutInterval


# ########################################## Define the PLD module #####################################################
def PLD(pdrop, pduplicate, pcorrupt, porder, pdelay):
    rand_drop = random()
    if rand_drop < pdrop:
        return 1
    else:
        rand_dupli = random()
        if rand_dupli < pduplicate:
            return 2
        else:
            rand_corrupt = random()
            if rand_corrupt < pcorrupt:
                return 3
            else:
                rand_order = random()
                if rand_order < porder:
                    return 4
                else:
                    rand_delay = random()
                    if rand_delay < pdelay:
                        return 5
                    else:
                        return 6

# ########################################## Preparing something to use and count ######################################

# Creating a UDP socket


try:
    senderSocket = socket(AF_INET, SOCK_DGRAM)
except:
    print("Failed to create receiver socket.")
    sys.exit()

# Creating a Sender_log file
sender_log = open("Sender_log.txt", "w")

#  Define some useful data to be counted
nb_of_trans_segments = 0  # Number of Data Segments Sent (including drop & RXT)
nb_of_ack_sent = 0  # Number of Ack Segments Sent
nb_of_PLD_handled = 0  # Number of Segments handled by PLD
nb_of_drop = 0  # Number of Segments Dropped
nb_of_corrupt = 0  # Number of Segments Corrupted
nb_of_reorder = 0  # Number of Segments Re-ordered
ordering_queue = []  # storing one segment to reorder the segments which is using in re-ordered PLD
nb_of_duplicate = 0  # Number of Segments Duplicated
nb_of_delay = 0  # Number of Segments Delayed
nb_of_timeout_retrans = 0  # Number of Retransmissions due to timeout
nb_of_fast_retrans = 0  # Number of Fast Retransmissions
nb_of_dup_ack = 0  # Number of Duplicate Acknowledgements received

if_receiving_segments = 0  # flag to confirm received ack
if_starting_timer = 0  # flag to start timer
if_segments_timeout = 0  # flag to justify timeout
if_finish_trans = 0  # flag to close receive thread
if_calculating_sampleRTT = 0  # flag to judge if the normal trans or re-trans, re-trans doesn't need to
#                               calculate sampleRTT


# ############################################ A three-way handshake ###################################################
sender_seq = 8  # initialise the sequence number of sender
start_time = time.time()

# first hand
first_hand = Segments(seq_value=sender_seq, syn=1)
senderSocket.sendto(first_hand.segment, (receiverHost, receiverPort))
curr_time = time.time()
time_to_log = (curr_time - start_time) * 1000
sender_log.writelines("snd  {:.3f}  S {:5d} {:3d} {:5d}\n".format(time_to_log, first_hand.SEQ_Value, len(first_hand.DATA), 0))
print("First handshake sending SYN...")
nb_of_trans_segments += 1
nb_of_ack_sent += 1

# second hand
second_hand, receiverAddress = senderSocket.recvfrom(2048)
second_hand_unpack = unpack_data(second_hand)
curr_time = time.time()
time_to_log = (curr_time - start_time) * 1000
sender_log.writelines("rcv  {:.3f}  SA{:5d} {:3d} {:5d}\n".format(time_to_log, second_hand_unpack.SEQ_Value,
                                                                  len(second_hand_unpack.DATA),
                                                                  second_hand_unpack.ACK_Value))

# third hand
if second_hand_unpack.SYN_Flag == 1 and second_hand_unpack.ACK_Flag == 1:
    print("Second handshake receiving SYNACK...")
    third_hand = Segments(seq_value=sender_seq + 1, ack=1, ack_value=second_hand_unpack.SEQ_Value + 1)
    senderSocket.sendto(third_hand.segment, (receiverHost, receiverPort))
    curr_time = time.time()
    time_to_log = (curr_time - start_time) * 1000
    sender_log.writelines("snd  {:.3f}  A {:5d} {:3d} {:5d}\n".format(time_to_log, third_hand.SEQ_Value, len(third_hand.DATA),
                                                                      third_hand.ACK_Value))
    nb_of_trans_segments += 1
    nb_of_ack_sent += 1
    print("Third handshake sending ACK...")
else:
    print("Connecting error!!")
    senderSocket.close()
    sys.exit()

# ############################################### Sending the file #####################################################

# Initialize the useful data from handshaking
seq_num = third_hand.SEQ_Value  # initialize the sequence value of the first segment
ack_num = third_hand.ACK_Value  # initialize the ack value of the first segment
sendbase = seq_num  # the sequence before sendbase is already received
LastByteAcked = seq_num  # ack last use for the newest ack segment received

# Getting file name and transmitting to receiver
file_name = sys.argv[3]
# file_name = 'test2.pdf'
f = open(file_name, 'rb')      # open file in binary
file_state = os.stat(file_name)
file_segements = []           # separating file and using list to store file
file_seq_num = seq_num
order = 0

# separating file by MSS and storing in a list
while order < file_state.st_size:
    message = f.read(mss)
    data = Segments(seq_value=file_seq_num, ack_value=ack_num, data=message)
    file_segements.append(data)
    file_seq_num += mss
    order += mss

# print(f'file len is {len(file_segements)}')

initial_timeout = 1       # initializing timeout value
timeout_interval = 1000     # initializing the timeout_interval(ms) value which is the result of using formula to calculate timeout
if_initial_timeout = 0        # judging if the formula is initializing or not
# senderSocket.settimeout(initial_timeout / 1000)      # initializing timeout

# ################################# Define sending thread and receiving thread #########################################

# Define the sending threading


class SenderThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global seq_num
        global LastByteAcked
        global sendbase
        global if_starting_timer
        global if_receiving_segments
        global if_segments_timeout
        global if_finish_trans
        global if_initial_timeout
        global if_calculating_sampleRTT
        global nb_of_trans_segments
        global nb_of_drop
        global nb_of_reorder
        global nb_of_duplicate
        global nb_of_corrupt
        global nb_waitting_seg
        global nb_of_delay
        global nb_of_timeout_retrans
        global nb_of_fast_retrans
        global sending_timer
        global start_time
        global stop_time
        global timeout_interval
        global ordering_queue

        i = 0
        while True:
            # transmitting data in the window
            while (seq_num - sendbase) <= mws and i < len(file_segements):
                if (seq_num + len(file_segements[i].DATA) - sendbase) > mws:
                    break
                # PLD module to operating segments
                results = PLD(pDrop, pDuplicate, pCorrupt, pOrder, pDelay)
                if results == 6:    # directly transmitting
                    senderSocket.sendto(file_segements[i].segment, (receiverHost, receiverPort))

                    # if timer does not start, start it
                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 1   # calculating the sampleRTT

                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("snd  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, file_segements[i].SEQ_Value,
                                                                                      len(file_segements[i].DATA),
                                                                                      file_segements[i].ACK_Value))
                    print("snd:     seq:{} ack:{}".format(file_segements[i].SEQ_Value, file_segements[i].ACK_Value))
                    nb_of_trans_segments += 1

                    # ordering_queue has a reorder segment to wait some other segments sending
                    # print(len(ordering_queue))
                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 1:    # waiting maxOrder segments
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))

                            # if timer does not start, start it
                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 1

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            # print(ordering_queue)
                            sender_log.writelines(
                                "rord  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))
                            nb_of_trans_segments += 1
                            nb_of_reorder += 1
                            nb_waitting_seg -= 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 1

                elif results == 1:       # dropping the segment
                    # if timer does not start, start it
                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 1

                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("drop {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, file_segements[i].SEQ_Value,
                                                                                      len(file_segements[i].DATA),
                                                                                      file_segements[i].ACK_Value))
                    print("drop:     seq:{} ack:{}".format(file_segements[i].SEQ_Value, file_segements[i].ACK_Value))
                    nb_of_trans_segments += 1
                    nb_of_drop += 1

                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 1:
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))
                            # if timer does not start, start it
                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 1

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rord  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))
                            nb_of_trans_segments += 1
                            nb_waitting_seg -= 1
                            nb_of_reorder += 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 1

                elif results == 2:           # duplicating the segment
                    senderSocket.sendto(file_segements[i].segment, (receiverHost, receiverPort))
                    senderSocket.sendto(file_segements[i].segment, (receiverHost, receiverPort))

                    # if timer does not start, start it
                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 1

                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("dup  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, file_segements[i].SEQ_Value,
                                                                                      len(file_segements[i].DATA),
                                                                                      file_segements[i].ACK_Value))
                    print("dup:     seq:{} ack:{}".format(file_segements[i].SEQ_Value, file_segements[i].ACK_Value))

                    nb_of_trans_segments += 2
                    nb_of_duplicate += 1

                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 2 or nb_waitting_seg == 1:
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))
                            # if timer does not start, start it
                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 1

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rord  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))
                            nb_of_trans_segments += 1
                            nb_waitting_seg = 0
                            nb_of_reorder += 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 2

                elif results == 3:              # corrupting data
                    sending_data = file_segements[i]
                    # in corrupted seg, we should get the old checksum from the correct seg.
                    old_checksum = sending_data.checksum
                    sending_corru_data = corrupted_bit(sending_data.DATA)

                    sending_corru_seg = Segments(syn=file_segements[i].SYN_Flag, ack=file_segements[i].ACK_Flag,
                                                 fin=file_segements[i].FIN_Flag, seq_value=file_segements[i].SEQ_Value,
                                                 ack_value=file_segements[i].ACK_Value, checksum_value=old_checksum,
                                                 checksum_flag=1, data=sending_corru_data)
                    senderSocket.sendto(sending_corru_seg.segment, (receiverHost, receiverPort))

                    # if timer does not start, start it
                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 1

                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("corr  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, sending_corru_seg.SEQ_Value
                                                                                       , len(sending_corru_seg.DATA),
                                                                                       sending_corru_seg.ACK_Value))
                    print("corr:     seq:{} ack:{}".format(sending_corru_seg.SEQ_Value, sending_corru_seg.ACK_Value))
                    nb_of_trans_segments += 1
                    nb_of_corrupt += 1

                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 1:
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))
                            # if timer does not start, start it
                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 1

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rord  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))
                            nb_of_trans_segments += 1
                            nb_waitting_seg -= 1
                            nb_of_reorder += 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 1

                elif results == 4:              # re-ordering data
                    if len(ordering_queue) == 0:
                        ordering_queue.append(file_segements[i])
                        nb_waitting_seg = maxOrder
                    else:
                        # The segment waiting to send is only one,
                        # so we should transmitting the first one when we get another one

                        senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))
                        # if timer does not start, start it
                        if if_starting_timer == 0:
                            sending_timer = time.time()
                            if_starting_timer = 1
                            if_calculating_sampleRTT = 1

                        curr_time = time.time()
                        time_to_log = (curr_time - start_time) * 1000
                        sender_log.writelines(
                            "rord  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                         len(ordering_queue[0].DATA),
                                                                         ordering_queue[0].ACK_Value))
                        print(
                            "rord:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))
                        nb_of_reorder += 1
                        ordering_queue = []
                        ordering_queue.append(file_segements[i])
                        nb_waitting_seg = maxOrder

                elif results == 5:              # delay
                    delay_time = uniform(0, maxDelay)         # random float [0-MaxDelay]
                    delay_time = delay_time / 1000              # ms -> s
                    time.sleep(delay_time)             # sleeping the thread so it can be delay to transmit
                    senderSocket.sendto(file_segements[i].segment, (receiverHost, receiverPort))

                    # if timer does not start, start it
                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 1

                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("dely  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, file_segements[i].SEQ_Value,
                                                                                      len(file_segements[i].DATA),
                                                                                      file_segements[i].ACK_Value))
                    print("dely:     seq:{} ack:{}".format(file_segements[i].SEQ_Value, file_segements[i].ACK_Value))

                    nb_of_trans_segments += 1
                    nb_of_delay += 1

                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 1:
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))
                            # if timer does not start, start it
                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 1

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rord  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))
                            nb_of_trans_segments += 1
                            nb_waitting_seg -= 1
                            nb_of_reorder += 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 1

                seq_num += len(file_segements[i].DATA)
                i += 1

            # to judging the timeout flag or received flag
            # if receiving segments, then using the real timeout to calculate the expected timeout
            while True:
                if if_receiving_segments == 1 and if_calculating_sampleRTT == 1:
                    receiving_timer = time.time()
                    real_time_cost = (receiving_timer - sending_timer) * 1000  # ms
                    if if_initial_timeout == 0:     # initializing the timeout formula
                        timeout_interval = timeout_value(real_time_cost, initial=True)
                        senderSocket.settimeout(timeout_interval/1000)
                        if_initial_timeout += 1
                    else:
                        timeout_interval = timeout_value(real_time_cost, initial=False)
                        senderSocket.settimeout(timeout_interval/1000)
                    if_segments_timeout = 0
                    break
                if if_segments_timeout == 1:
                    if_receiving_segments = 0
                    if_segments_timeout = 0
                    break

                stop_time = time.time()         # timeout
                if (stop_time - sending_timer) >= timeout_interval / 1000:
                    # print(initial_timeout)
                    print("timeout")
                    if_receiving_segments = 0
                    break

            # print("Judging retransmitting or not...")

            # if timeout then retransmitting the segments
            if if_receiving_segments == 0:
                m = int((LastByteAcked - third_hand.SEQ_Value) / mss)
                # print(f'{LastByteAcked}')
                if m >= len(file_segements):  # if finished transmitting but sender thread has not yet
                    break                     # implemented a jump out

                results = PLD(pDrop, pDuplicate, pCorrupt, pOrder, pDelay)

                if results == 6:
                    # print(file_segements[m])
                    senderSocket.sendto(file_segements[m].segment, (receiverHost, receiverPort))
                    # retransmitting doesn't need to calculate the sampleRTT
                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 0

                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("snd/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, file_segements[m].SEQ_Value,
                                                                                      len(file_segements[m].DATA),
                                                                                      file_segements[m].ACK_Value))
                    print("snd&RXT:     seq:{} ack:{}".format(file_segements[m].SEQ_Value, file_segements[m].ACK_Value))
                    nb_of_timeout_retrans += 1
                    nb_of_trans_segments += 1

                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 1:
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord&RXT:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))

                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 0

                            nb_of_trans_segments += 1
                            nb_of_timeout_retrans += 1
                            nb_waitting_seg -= 1
                            nb_of_reorder += 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 1

                elif results == 1:  # dropping the segment
                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("drop/RXT {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, file_segements[m].SEQ_Value,
                                                                                      len(file_segements[m].DATA),
                                                                                      file_segements[m].ACK_Value))
                    print("drop&RXT:     seq:{} ack:{}".format(file_segements[m].SEQ_Value, file_segements[m].ACK_Value))

                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 0

                    nb_of_trans_segments += 1
                    nb_of_drop += 1
                    nb_of_timeout_retrans += 1

                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 1:
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))

                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 0

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord&RXT:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))
                            nb_of_trans_segments += 1
                            nb_of_timeout_retrans += 1
                            nb_of_reorder += 1
                            nb_waitting_seg -= 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 1

                elif results == 2:  # duplicating the segment
                    senderSocket.sendto(file_segements[m].segment, (receiverHost, receiverPort))
                    senderSocket.sendto(file_segements[m].segment, (receiverHost, receiverPort))

                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 0

                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("dup/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, file_segements[m].SEQ_Value,
                                                                                      len(file_segements[m].DATA),
                                                                                      file_segements[m].ACK_Value))
                    print("dup&RXT:     seq:{} ack:{}".format(file_segements[m].SEQ_Value, file_segements[m].ACK_Value))
                    nb_of_trans_segments += 2
                    nb_of_duplicate += 1
                    nb_of_timeout_retrans += 1

                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 2 or nb_waitting_seg == 1:
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord&RXT:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))

                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 0

                            nb_of_trans_segments += 1
                            nb_waitting_seg = 0
                            nb_of_timeout_retrans += 1
                            nb_of_reorder += 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 2

                elif results == 3:  # corrupting data
                    sending_data = file_segements[m]
                    # in corrupted seg, we should get the old checksum from the correct seg.
                    old_checksum = sending_data.checksum
                    sending_corru_data = corrupted_bit(sending_data.DATA)
                    sending_corru_seg = Segments(syn=file_segements[m].SYN_Flag, ack=file_segements[m].ACK_Flag,
                                                 fin=file_segements[m].FIN_Flag, seq_value=file_segements[m].SEQ_Value,
                                                 ack_value=file_segements[m].ACK_Value, checksum_value=old_checksum,
                                                 checksum_flag=1, data=sending_corru_data)
                    senderSocket.sendto(sending_corru_seg.segment, (receiverHost, receiverPort))

                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 0

                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("corr/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, sending_corru_seg.SEQ_Value
                                                                                       , len(sending_corru_seg.DATA),
                                                                                       sending_corru_seg.ACK_Value))
                    print("corr&RXT:     seq:{} ack:{}".format(sending_corru_seg.SEQ_Value, sending_corru_seg.ACK_Value))
                    nb_of_trans_segments += 1
                    nb_of_corrupt += 1
                    nb_of_timeout_retrans += 1

                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 1:
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord&RXT:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))

                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 0

                            nb_of_trans_segments += 1
                            nb_waitting_seg -= 1
                            nb_of_timeout_retrans += 1
                            nb_of_reorder += 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 1

                elif results == 4:  # re-ordering data
                    if len(ordering_queue) == 0:
                        ordering_queue.append(file_segements[m])
                        nb_waitting_seg = maxOrder
                    else:
                        senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))

                        curr_time = time.time()
                        time_to_log = (curr_time - start_time) * 1000
                        sender_log.writelines(
                            "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                         len(ordering_queue[0].DATA),
                                                                         ordering_queue[0].ACK_Value))
                        print(
                            "rord&RXT:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))

                        if if_starting_timer == 0:
                            sending_timer = time.time()
                            if_starting_timer = 1
                            if_calculating_sampleRTT = 0

                        ordering_queue = []
                        ordering_queue.append(file_segements[m])
                        nb_waitting_seg = maxOrder
                        nb_of_trans_segments += 1
                        nb_of_timeout_retrans += 1
                        nb_of_reorder += 1

                elif results == 5:              # delay
                    delay_time = uniform(0, maxDelay)         # random float [0-MaxDelay]
                    delay_time = delay_time / 1000
                    time.sleep(delay_time)
                    senderSocket.sendto(file_segements[m].segment, (receiverHost, receiverPort))

                    curr_time = time.time()
                    time_to_log = (curr_time - start_time) * 1000
                    sender_log.writelines("dely/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, file_segements[m].SEQ_Value,
                                                                                      len(file_segements[m].DATA),
                                                                                      file_segements[m].ACK_Value))
                    print("dely/RXT:     seq:{} ack:{}".format(file_segements[m].SEQ_Value, file_segements[m].ACK_Value))

                    if if_starting_timer == 0:
                        sending_timer = time.time()
                        if_starting_timer = 1
                        if_calculating_sampleRTT = 0

                    nb_of_trans_segments += 1
                    nb_of_delay += 1
                    nb_of_timeout_retrans += 1

                    if len(ordering_queue) == 1:
                        if nb_waitting_seg == 1:
                            senderSocket.sendto(ordering_queue[0].segment, (receiverHost, receiverPort))

                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log, ordering_queue[0].SEQ_Value,
                                                                             len(ordering_queue[0].DATA),
                                                                             ordering_queue[0].ACK_Value))
                            print(
                                "rord&RXT:     seq:{} ack:{}".format(ordering_queue[0].SEQ_Value, ordering_queue[0].ACK_Value))

                            if if_starting_timer == 0:
                                sending_timer = time.time()
                                if_starting_timer = 1
                                if_calculating_sampleRTT = 0

                            nb_of_trans_segments += 1
                            nb_waitting_seg -= 1
                            nb_of_timeout_retrans += 1
                            nb_of_reorder += 1
                            ordering_queue = []
                        else:
                            nb_waitting_seg -= 1
                continue

            # if receive the correct response then continue
            if_receiving_segments = 0
            if_starting_timer = 0
            # if at the end of the file then break
            if if_finish_trans == 1:
                break


# Define the receiving threading
class ReceiverThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global seq_num
        global LastByteAcked
        global sendbase
        global if_starting_timer
        global if_segments_timeout
        global if_finish_trans
        global if_receiving_segments
        global if_calculating_sampleRTT
        global nb_of_dup_ack
        global nb_of_trans_segments
        global nb_of_drop
        global nb_of_duplicate
        global nb_of_reorder
        global nb_waitting_seg
        global nb_of_corrupt
        global nb_of_delay
        global nb_of_fast_retrans
        global sending_timer
        global start_time

        j = 0
        ordering_queue_receiver = []
        while True:
            # if the timer is working
            if if_starting_timer == 1:
                try:
                    response, receiverAddress = senderSocket.recvfrom(2048)
                    response_unpack = unpack_data(response)
                    if response_unpack.ACK_Flag == 1:
                        # changing the last received ack value, which equal to the next needed sequence number
                        LastByteAcked = response_unpack.ACK_Value

                        # cumulative acknowledgement: if received a bigger ack,
                        # which means we received all of the segments before this ack and then changing the sendbase
                        if response_unpack.ACK_Value > sendbase:
                            curr_time = time.time()
                            time_to_log = (curr_time - start_time) * 1000
                            sender_log.writelines(
                                "rcv  {:.3f}  A {:5d} {:3d} {:5d}\n".format(time_to_log, response_unpack.SEQ_Value,
                                                                            len(response_unpack.DATA),
                                                                            response_unpack.ACK_Value))
                            print("rcv:  seq:{} ack:{}".format(response_unpack.SEQ_Value, response_unpack.ACK_Value))
                            j = 1
                            sendbase = response_unpack.ACK_Value
                            if_receiving_segments = 1         # changing the flag of received
                            # if existing unacked segments, starting timer
                            if seq_num != sendbase:
                                sending_timer = time.time()
                                if_starting_timer = 1
                        else:
                            # fast retransmitting: if received same ack number three times,
                            # then retransmitting the segments
                            if response_unpack.ACK_Value == sendbase:
                                j += 1
                                nb_of_dup_ack += 1

                                curr_time = time.time()
                                time_to_log = (curr_time - start_time) * 1000
                                sender_log.writelines("rcv/DA  {:.3f}  A {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                     response_unpack.SEQ_Value,
                                                                                                     len(response_unpack.DATA),
                                                                                                     response_unpack.ACK_Value))
                                print("rcv&DA:     seq:{} ack:{}".format(response_unpack.SEQ_Value,
                                                                         response_unpack.ACK_Value))
                                if j >= 3:
                                    j = 0

                                    # Fast retransmitting
                                    # using the last received ack value to find the correct segments we want to send
                                    m = int((LastByteAcked - third_hand.SEQ_Value) / mss)

                                    results = PLD(pDrop, pDuplicate, pCorrupt, pOrder, pDelay)
                                    if results == 6:
                                        senderSocket.sendto(file_segements[m].segment, (receiverHost, receiverPort))
                                        # retransmitting doesn't need to calculate SampleRTT

                                        curr_time = time.time()
                                        time_to_log = (curr_time - start_time) * 1000
                                        sender_log.writelines("snd/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                          file_segements[m].SEQ_Value,
                                                                                                          len(file_segements[m].DATA),
                                                                                                          file_segements[m].ACK_Value))
                                        print("snd&RXT:     seq:{} ack:{}".format(file_segements[m].SEQ_Value,
                                                                               file_segements[m].ACK_Value))

                                        if if_starting_timer == 0:
                                            sending_timer = time.time()
                                            if_starting_timer = 1
                                            if_calculating_sampleRTT = 0

                                        nb_of_fast_retrans += 1
                                        nb_of_trans_segments += 1

                                        if len(ordering_queue_receiver) == 1:
                                            if nb_waitting_seg == 1:
                                                senderSocket.sendto(ordering_queue_receiver[0].segment,
                                                                    (receiverHost, receiverPort))

                                                curr_time = time.time()
                                                time_to_log = (curr_time - start_time) * 1000
                                                # print(ordering_queue_receiver)
                                                sender_log.writelines(
                                                    "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                 ordering_queue_receiver[0].SEQ_Value,
                                                                                                 len(ordering_queue_receiver[0].DATA),
                                                                                                 ordering_queue_receiver[0].ACK_Value))
                                                print(
                                                    "rord&RXT:     seq:{} ack:{}".format(ordering_queue_receiver[0].SEQ_Value,
                                                                                     ordering_queue_receiver[0].ACK_Value))

                                                if if_starting_timer == 0:
                                                    sending_timer = time.time()
                                                    if_starting_timer = 1
                                                    if_calculating_sampleRTT = 0

                                                nb_of_trans_segments += 1
                                                nb_of_fast_retrans += 1
                                                nb_of_reorder += 1
                                                nb_waitting_seg -= 1
                                                ordering_queue_receiver = []
                                            else:
                                                nb_waitting_seg -= 1

                                    elif results == 1:  # dropping the segment
                                        curr_time = time.time()
                                        time_to_log = (curr_time - start_time) * 1000
                                        sender_log.writelines("drop/RXT {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                          file_segements[m].SEQ_Value,
                                                                                                          len(file_segements[m].DATA),
                                                                                                          file_segements[m].ACK_Value))
                                        print("drop&RXT:     seq:{} ack:{}".format(file_segements[m].SEQ_Value,
                                                                               file_segements[m].ACK_Value))

                                        if if_starting_timer == 0:
                                            sending_timer = time.time()
                                            if_starting_timer = 1
                                            if_calculating_sampleRTT = 0

                                        nb_of_trans_segments += 1
                                        nb_of_drop += 1
                                        nb_of_fast_retrans += 1

                                        if len(ordering_queue_receiver) == 1:
                                            if nb_waitting_seg == 1:
                                                senderSocket.sendto(ordering_queue_receiver[0].segment, (receiverHost, receiverPort))

                                                curr_time = time.time()
                                                time_to_log = (curr_time - start_time) * 1000
                                                sender_log.writelines(
                                                    "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                 ordering_queue_receiver[0].SEQ_Value,
                                                                                                 len(ordering_queue_receiver[0].DATA),
                                                                                                 ordering_queue_receiver[0].ACK_Value))
                                                print(
                                                    "rord&RXT:     seq:{} ack:{}".format(ordering_queue_receiver[0].SEQ_Value,
                                                                                     ordering_queue_receiver[0].ACK_Value))

                                                if if_starting_timer == 0:
                                                    sending_timer = time.time()
                                                    if_starting_timer = 1
                                                    if_calculating_sampleRTT = 0

                                                nb_of_trans_segments += 1
                                                nb_waitting_seg -= 1
                                                nb_of_fast_retrans += 1
                                                nb_of_reorder += 1
                                                ordering_queue_receiver = []
                                            else:
                                                nb_waitting_seg -= 1

                                    elif results == 2:  # duplicating the segment
                                        senderSocket.sendto(file_segements[m].segment, (receiverHost, receiverPort))
                                        senderSocket.sendto(file_segements[m].segment, (receiverHost, receiverPort))

                                        curr_time = time.time()
                                        time_to_log = (curr_time - start_time) * 1000
                                        sender_log.writelines("dup/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                          file_segements[m].SEQ_Value,
                                                                                                          len(file_segements[m].DATA),
                                                                                                          file_segements[m].ACK_Value))
                                        print("dup&RXT:     seq:{} ack:{}".format(file_segements[m].SEQ_Value,
                                                                              file_segements[m].ACK_Value))

                                        if if_starting_timer == 0:
                                            sending_timer = time.time()
                                            if_starting_timer = 1
                                            if_calculating_sampleRTT = 0

                                        nb_of_trans_segments += 2
                                        nb_of_duplicate += 1
                                        nb_of_fast_retrans += 1

                                        if len(ordering_queue_receiver) == 1:
                                            if nb_waitting_seg == 2 or nb_waitting_seg == 1:
                                                senderSocket.sendto(ordering_queue_receiver[0].segment,
                                                                    (receiverHost, receiverPort))

                                                curr_time = time.time()
                                                time_to_log = (curr_time - start_time) * 1000
                                                sender_log.writelines(
                                                    "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                 ordering_queue_receiver[0].SEQ_Value,
                                                                                                 len(ordering_queue_receiver[0].DATA),
                                                                                                 ordering_queue_receiver[0].ACK_Value))
                                                print(
                                                    "rord&RXT:     seq:{} ack:{}".format(ordering_queue_receiver[0].SEQ_Value,
                                                                                     ordering_queue_receiver[0].ACK_Value))

                                                if if_starting_timer == 0:
                                                    sending_timer = time.time()
                                                    if_starting_timer = 1
                                                    if_calculating_sampleRTT = 0

                                                nb_of_trans_segments += 1
                                                nb_waitting_seg = 0
                                                nb_of_fast_retrans += 1
                                                nb_of_reorder += 1
                                                ordering_queue_receiver = []
                                            else:
                                                nb_waitting_seg -= 2

                                    elif results == 3:  # corrupting data
                                        sending_data = file_segements[m]
                                        # in corrupted seg, we should get the old checksum from the correct seg.
                                        old_checksum = sending_data.checksum
                                        sending_corru_data = corrupted_bit(sending_data.DATA)
                                        sending_corru_seg = Segments(syn=file_segements[m].SYN_Flag,
                                                                     ack=file_segements[m].ACK_Flag,
                                                                     fin=file_segements[m].FIN_Flag,
                                                                     seq_value=file_segements[m].SEQ_Value,
                                                                     ack_value=file_segements[m].ACK_Value,
                                                                     checksum_value=old_checksum,
                                                                     checksum_flag=1, data=sending_corru_data)
                                        senderSocket.sendto(sending_corru_seg.segment, (receiverHost, receiverPort))

                                        curr_time = time.time()
                                        time_to_log = (curr_time - start_time) * 1000
                                        sender_log.writelines("corr/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                           sending_corru_seg.SEQ_Value,
                                                                                                           len(sending_corru_seg.DATA),
                                                                                                           sending_corru_seg.ACK_Value))
                                        print("corr&RXT:     seq:{} ack:{}".format(sending_corru_seg.SEQ_Value,
                                                                               sending_corru_seg.ACK_Value))

                                        if if_starting_timer == 0:
                                            sending_timer = time.time()
                                            if_starting_timer = 1
                                            if_calculating_sampleRTT = 0

                                        nb_of_trans_segments += 1
                                        nb_of_corrupt += 1
                                        nb_of_fast_retrans += 1

                                        if len(ordering_queue_receiver) == 1:
                                            if nb_waitting_seg == 1:
                                                senderSocket.sendto(ordering_queue_receiver[0].segment,
                                                                    (receiverHost, receiverPort))

                                                curr_time = time.time()
                                                time_to_log = (curr_time - start_time) * 1000
                                                sender_log.writelines(
                                                    "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                 ordering_queue_receiver[0].SEQ_Value,
                                                                                                 len(ordering_queue_receiver[0].DATA),
                                                                                                 ordering_queue_receiver[0].ACK_Value))
                                                print(
                                                    "rord&RXT:     seq:{} ack:{}".format(ordering_queue_receiver[0].SEQ_Value,
                                                                                     ordering_queue_receiver[0].ACK_Value))

                                                if if_starting_timer == 0:
                                                    sending_timer = time.time()
                                                    if_starting_timer = 1
                                                    if_calculating_sampleRTT = 0

                                                nb_of_trans_segments += 1
                                                nb_waitting_seg -= 1
                                                nb_of_fast_retrans += 1
                                                nb_of_reorder += 1
                                                ordering_queue_receiver = []
                                            else:
                                                nb_waitting_seg -= 1

                                    elif results == 4:  # re-ordering data
                                        if len(ordering_queue_receiver) == 0:
                                            ordering_queue_receiver.append(file_segements[m])
                                            nb_waitting_seg = maxOrder
                                        else:
                                            senderSocket.sendto(ordering_queue_receiver[0].segment, (receiverHost, receiverPort))

                                            curr_time = time.time()
                                            time_to_log = (curr_time - start_time) * 1000
                                            sender_log.writelines(
                                                "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                             ordering_queue_receiver[0].SEQ_Value,
                                                                                             len(ordering_queue_receiver[0].DATA),
                                                                                             ordering_queue_receiver[0].ACK_Value))
                                            print(
                                                "rord&RXT:     seq:{} ack:{}".format(ordering_queue_receiver[0].SEQ_Value,
                                                                                 ordering_queue_receiver[0].ACK_Value))

                                            if if_starting_timer == 0:
                                                sending_timer = time.time()
                                                if_starting_timer = 1
                                                if_calculating_sampleRTT = 0

                                            ordering_queue_receiver = []
                                            ordering_queue_receiver.append(file_segements[m])
                                            nb_waitting_seg = maxOrder
                                            nb_of_fast_retrans += 1
                                            nb_of_reorder += 1

                                    elif results == 5:  # delay
                                        delay_time = uniform(0, maxDelay)  # random float [0-MaxDelay]
                                        delay_time = delay_time / 1000
                                        time.sleep(delay_time)
                                        senderSocket.sendto(file_segements[m].segment, (receiverHost, receiverPort))

                                        curr_time = time.time()
                                        time_to_log = (curr_time - start_time) * 1000
                                        sender_log.writelines("dely/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                           file_segements[m].SEQ_Value,
                                                                                                           len(file_segements[m].DATA),
                                                                                                           file_segements[m].ACK_Value))
                                        print("dely&RXT:     seq:{} ack:{}".format(file_segements[m].SEQ_Value,
                                                                               file_segements[m].ACK_Value))

                                        if if_starting_timer == 0:
                                            sending_timer = time.time()
                                            if_starting_timer = 1
                                            if_calculating_sampleRTT = 0

                                        nb_of_trans_segments += 1
                                        nb_of_delay += 1
                                        nb_of_fast_retrans += 1

                                        if len(ordering_queue_receiver) == 1:
                                            if nb_waitting_seg == 1:
                                                senderSocket.sendto(ordering_queue_receiver[0].segment,
                                                                    (receiverHost, receiverPort))

                                                curr_time = time.time()
                                                time_to_log = (curr_time - start_time) * 1000
                                                sender_log.writelines(
                                                 "rord/RXT  {:.3f}  D {:5d} {:3d} {:5d}\n".format(time_to_log,
                                                                                                 ordering_queue_receiver[0].SEQ_Value,
                                                                                                 len(ordering_queue_receiver[0].DATA),
                                                                                                 ordering_queue_receiver[0].ACK_Value))
                                                print(
                                                    "rord&RXT:     seq:{} ack:{}".format(ordering_queue_receiver[0].SEQ_Value,
                                                                                     ordering_queue_receiver[0].ACK_Value))

                                                if if_starting_timer == 0:
                                                    sending_timer = time.time()
                                                    if_starting_timer = 1
                                                    if_calculating_sampleRTT = 0

                                                nb_of_trans_segments += 1
                                                nb_waitting_seg -= 1
                                                nb_of_fast_retrans += 1
                                                nb_of_reorder += 1
                                                ordering_queue_receiver = []
                                            else:
                                                nb_waitting_seg -= 1

                            else:
                                j = 0

                        # if at the end of the file, break
                        if response_unpack.ACK_Value >= third_hand.SEQ_Value + file_state.st_size:
                            if_finish_trans = 1
                            break
                # no received response, wait for timeout
                except timeout:

                    # if there is already a timer working, we just need to wait it
                    if if_starting_timer == 1:
                        continue

                    # if no timer working and the socket timeout, return timeout flag and restransfer the segment
                    if_segments_timeout = 1
                    continue


# thread working(normal format)
threads = []
sending_thread = SenderThread()
receiving_thread = ReceiverThread()
sending_thread.start()
receiving_thread.start()
threads.append(sending_thread)
threads.append(receiving_thread)
for t in threads:
    t.join()

# ############################## Four-segment connection termination ###################################################

# if at the end of the file
if if_finish_trans == 1:
    print("Completed transmission...")

    # send fin flag
    first_end = Segments(seq_value=third_hand.SEQ_Value + file_state.st_size, ack_value=ack_num, fin=1)
    senderSocket.sendto(first_end.segment, (receiverHost, receiverPort))
    curr_time = time.time()
    time_to_log = (curr_time - start_time) * 1000
    sender_log.writelines("snd  {:.3f}  F {:5d} {:3d} {:5d}\n".format(time_to_log, first_end.SEQ_Value, len(first_end.DATA),
                                                                      first_end.ACK_Value))
    print("Sending FIN and waiting response ACK...")
    nb_of_trans_segments += 1
    nb_of_ack_sent += 1

    # receiving ack flag
    second_end, receiverAddress = senderSocket.recvfrom(2048)
    second_end_unpack = unpack_data(second_end)
    print("Receiving ACK and waiting FINACK...")
    if second_end_unpack.ACK_Flag == 1:
        # receiving fin flag
        third_end, receiverAddress = senderSocket.recvfrom(2048)
        third_end_unpack = unpack_data(third_end)
        if third_end_unpack.FIN_Flag == 1 and third_end_unpack.ACK_Flag == 1:
            curr_time = time.time()
            time_to_log = (curr_time - start_time) * 1000
            sender_log.writelines(
                "rcv  {:.3f}  FA{:5d} {:3d} {:5d}\n".format(time_to_log, third_end_unpack.SEQ_Value, len(third_end_unpack.DATA),
                                                            third_end_unpack.ACK_Value))
            print("Receiving FINACK and sending ACK...")

    # sending ack flag
    forth_end = Segments(seq_value=third_end_unpack.ACK_Value, ack=1, ack_value=third_end_unpack.SEQ_Value + 1)
    senderSocket.sendto(forth_end.segment, (receiverHost, receiverPort))
    curr_time = time.time()
    time_to_log = (curr_time - start_time) * 1000
    sender_log.writelines(
        "snd  {:.3f}  A {:5d} {:3d} {:5d}\n".format(time_to_log, forth_end.SEQ_Value, len(forth_end.DATA),
                                                    forth_end.ACK_Value))
    nb_of_trans_segments += 1
    nb_of_ack_sent += 1
    print("close sender...")

    # wait for a timeout, then shut down
    time.sleep(initial_timeout / 1000)
    senderSocket.close()
    # writing the statistics
    sender_log.writelines("Size of the file (in Bytes): %d\n" % file_state.st_size)
    sender_log.writelines("Segments transmitted (including drop & RXT): %d\n" % nb_of_trans_segments)
    sender_log.writelines("Number of Segments handled by PLD: %d\n" % (nb_of_trans_segments - nb_of_ack_sent))
    sender_log.writelines("Number of Segments Dropped: %d\n" % nb_of_drop)
    sender_log.writelines("Number of Segments Corrupted: %d\n" % nb_of_corrupt)
    sender_log.writelines("Number of Segments Re-ordered: %d\n" % nb_of_reorder)
    sender_log.writelines("Number of Segments Duplicated: %d\n" % nb_of_duplicate)
    sender_log.writelines("Number of Segments Delayed: %d\n" % nb_of_delay)
    sender_log.writelines("Number of Retransmissions due to timeout: %d\n" % nb_of_timeout_retrans)
    sender_log.writelines("Number of Fast Retransmissions: %d\n" % nb_of_fast_retrans)
    sender_log.writelines("Number of Duplicate Acknowledgements received: %d\n" % nb_of_dup_ack)
    f.close()
    sender_log.close()
