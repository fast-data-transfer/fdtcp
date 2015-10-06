package authenticator;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.File;
import java.io.PrintWriter;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.net.InetAddress;
import java.net.Socket;
import java.util.Map;
import java.net.UnknownHostException;

import org.globus.common.CoGProperties;

import lia.util.net.common.Config;
import lia.util.net.common.Utils;

import lia.gsi.net.GSIGssSocketFactory;

import authenticator.common.ResponseMsg;


/**
 * AuthClient - class for GSI authentication (using FDT GSI authentication)
 * 
 * Takes GSI credentials from
 *  o X509_CERT_DIR - directory with CA certificates (property value)
 *  o X509_USER_PROXY - user's proxy (property value)
 *  
 * Command line arguments: -p <port> -h <remoteservicehost> -u <fileNameToStoreRemoteUserName>
 *      fileNameToStoreRemoteUserName - client stores into this temporary file
 *      user name from the remote site and this information is name
 *      is then forwarded to fdtd which doesn't have to another mapping.
 * 
 * @author Zdenek Maxa
 *
 */
public class AuthClient
{
    
    
    public static void printUsage()
    {
        System.out.println(
"usage: -h <remote-authservice-host> -p <port> -f <file-at-remote-host-to-store-user-proxy> -u <local-file-to-store-remote-user-name>");
    }
    
    
    
    public static void checkInputOptions(Map<String, Object> argsMap)
    {
        if(argsMap.get("-p") == null)
        {
            printUsage();
            throw new IllegalArgumentException("No port specified, exit.");
        }

        if(argsMap.get("-h") == null)
        {
            printUsage();
            throw new IllegalArgumentException("No auth service host specified, exit.");
        }

        if(argsMap.get("-u") == null)
        {
            printUsage();
            throw new IllegalArgumentException("No temp file name to store remote user name specified, exit.");
        }        
    }

        
        
    public static void main(String[] args) throws UnknownHostException, ClassNotFoundException
    {
        
        Map<String, Object> argsMap = Utils.parseArguments(args, Config.SINGLE_CMDLINE_ARGS);
        checkInputOptions(argsMap);

        int port = Integer.valueOf((String) argsMap.get("-p"));        
        String host = (String) argsMap.get("-h");
        String fileNameToStoreRemoteUserName = (String) argsMap.get("-u");         
            
        try
        {
            System.out.println("Initiating the authentication process, waiting for response from service ...");
            
            GSIGssSocketFactory factory = new GSIGssSocketFactory();
            Socket socket = factory.createSocket(InetAddress.getByName(host), port, false, false);
            
            InputStream is = socket.getInputStream();
            ObjectInputStream ois = new ObjectInputStream(is);
            ResponseMsg response = (ResponseMsg) ois.readObject();
            
            System.out.println("Data received: " + response);
            
            if(response.getStatusCode() != 0)
            {
                System.out.println("AuthClient failled, non-zero status code from remote service, exit.");
                System.exit(response.getStatusCode());
            }
            
            // store the user name of the remote grid user (remote from fdtcp
            // perspective) into an temp file so that remote fdtd party will
            // not have to look up the mapping service again
            System.out.println("Going to store a file with remote user name into " +
                               fileNameToStoreRemoteUserName + " ...");
            
            FileWriter fw = new FileWriter(fileNameToStoreRemoteUserName, true);
            fw.write(response.getLocalUserName());
            fw.flush();
            fw.close();
            
            System.out.println("AuthClient finished successfully.");
            
            System.exit(response.getStatusCode());
        }
        catch(IOException ioe)
        {
            System.out.println("Authentication failed, reason: " + ioe.getMessage());
            ioe.printStackTrace();
            System.exit(1);
        }              
    }
}