import java.io.*;
import java.net.*;
import java.util.*;

public class PingClient {
    private static final int TIMEOUT=1000;   // Timeout is 1 second.
    public static void main(String[] args) throws IOException {
		 if (args.length != 2) {
         System.out.println("Required arguments: Server's address and port");
         return;
      }
	  InetAddress address = InetAddress.getByName(args[0]);
	  int port = Integer.parseInt(args[1]);
	  
         long RTTarr[] = new long[10];       //store RTT array to compare max,min,ave.
         int num_of_RTTarr=0;
        for (int i = 0; i < 10; i++){              //10 packets
        long startTime = System.currentTimeMillis();         
        String msg = "PING " + i + " "+ startTime+" \r\n";         //message
        byte[] data = msg.getBytes();
        DatagramSocket socket = new DatagramSocket();
      // set timeout(1 second)to make client infer whether it is timeout.
        socket.setSoTimeout(TIMEOUT);
        // create packets including message, ip address and port.
        DatagramPacket sendPacket = new DatagramPacket(data, data.length, address, port);

        byte[] data2 = new byte[1024];
        DatagramPacket receivePacket =              // null packets to receive.
                  new DatagramPacket(data2, data2.length);
        boolean receivedResponse = false;             
        socket.send(sendPacket);
         try{
                   socket.receive(receivePacket);   
                   receivedResponse = true;          //gets resopnse
              } catch(InterruptedIOException e){          //if not gets, print timeout.
                     System.out.println("ping to 127.0.0.1, seq = " + i + ", Timed out" ); 
                                                                   }
         if (receivedResponse) {        //if gets, execute this function.
            long finishTime = System.currentTimeMillis();        //calculate the RTT.
            long RTT = finishTime - startTime;
            RTTarr[num_of_RTTarr] = RTT ;               //store the RTT to compare.
            num_of_RTTarr++;
           System.out.println("ping to 127.0.0.1,seq = " + i + " rtt = " + RTT +"ms");    //print result.
         } 
}
        long min,max,sum,ave;   //RTT of max,min,ave.
        min=max=RTTarr[0];
        sum=0;
        for(int k = 0; k < num_of_RTTarr; k++)
        {
         if(RTTarr[k]>max)
         max=RTTarr[k];
         if(RTTarr[k]<min)
         min=RTTarr[k];
         sum = sum + RTTarr[k];
        }
        ave = sum/(num_of_RTTarr);
        System.out.println("min RTT:"+min+"ms, max RTT:"+max+"ms, Ave RTT:"+ave+"ms");  
        // close 
       // socket.close();
    }
}
