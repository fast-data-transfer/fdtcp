package authenticator;

import java.io.File;
import java.io.IOException;
import java.io.PrintWriter;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.io.BufferedReader;
import java.io.FileOutputStream;
import java.io.FileWriter;
import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.net.InetAddress;
import java.util.Map;
import java.util.Set;
import java.util.logging.Level;

import java.security.Principal;
import javax.security.auth.Subject;

import org.globus.gsi.GSIConstants;
import org.globus.gsi.GlobusCredential;
import org.globus.gsi.GlobusCredentialException;
import org.globus.gsi.gssapi.GlobusGSSCredentialImpl;
import org.globus.gsi.jaas.UserNamePrincipal;
import org.ietf.jgss.GSSCredential;
import org.ietf.jgss.GSSException;

import lia.gsi.net.GSIBaseServer;
import lia.gsi.GSIServer;
import lia.gsi.net.Peer;
import lia.util.net.common.Config;
import lia.util.net.common.Utils;

import authenticator.common.ResponseMsg;



/**
 * AuthService - application running at the fdtd side, provides authentication
 * for AuthClient running at fdtcp side.
 * 
 * GSI authentication uses following items to establish authentication capabilities:
 *  o X509_CERT_DIR - directory with certificates of CAs
 *  o X509_SERVICE_KEY
 *  o X509_SERVICE_CERT
 *  o GRIDMAP - against entries in this file is performed authentication, the file
 *      is queried by the GSI libraries
 *  
 * These values are specified as property values.
 * 
 * @author Zdenek Maxa
 * 
 */
public class AuthService extends GSIServer
{
    
    public AuthService(int port) throws Exception
    {
        super(port);
        
        // check if GRIDMAP exists and if not fail here, otherwise GSI libbs would
        // hang forever if the file doesn't exist
        // do not perform this check now, causes issues during cluster automated
        // installation when grid mapfile is not present when starting up
        // fdtd and this AuthService but will be at the time of transfer
        // GSI auth hanging due to non-existent grid mapfile was taken
        // care of in FDT Java ...
        /*
        String fileName = System.getProperty("GRIDMAP");
        File tmpCheck = new File(fileName);
        if(! tmpCheck.exists())
        {
            throw new Exception("Grid map file " + fileName + " does not exist.");
        }
        */
    }
    
    
    // TODO
    // this stops the server but doesn't stop client threads (see comment in GSIServer)
    // thus stopping the AuthService via SIGTERM, the ShutdownHook gets run fine, but
    // the application is still running
    // have to investigate how to stop client threads
    // for the moment have to stop AuthService by SIGKILL which means that ShutdownHook
    // doesn't get run
    public void stopService()
    {
        this.shutdown();
    }
    
    
    /**
     * Handles individual client connections by starting a different thread.
     * 
     * @param socket
     *            is connected to a client ready to send request to the gatekeeper.
     * @throws IOException
     *             if authentication/authorization exception
     */
    protected void handleConnection(Peer peer)
    {
        Socket socket = peer.getSocket();
        Subject peerSubject = null;
        System.out.println("Client connected: " + socket.getInetAddress() + ":" + socket.getPort());
        // in order to start the SSL handshake we need to call socket.getInput(Output)Stream()
        try 
        {
            socket.getOutputStream();
            socket.getInputStream();
            // peer.authorizer called
            peerSubject = peer.getPeerSubject();
        } 
        catch(IOException e) 
        {
            // TODO
            // is there a way send any info to the client as to what happened here?
            System.out.println("Authentication failed: " + e);
            e.printStackTrace();
            if(!socket.isClosed()) 
            {
                try
                {
                    socket.close();
                    System.out.println("Client disconnected.");
                } 
                catch(IOException e1)
                {
                    e1.printStackTrace();
                }
            }
            return;
        }

        // the client is successfully authenticated and authorized
        // so, proceed with the actual control conversation
        handleConversation(this, socket, peerSubject);
    }
        
    
    
    protected void handleConversation(AuthService parent, Socket client, Subject peerSubject)
    {
        String localUserName = null;
        
        System.out.println("Client connected :" + client + "\n" + peerSubject);
        if(peerSubject != null)
        {
            // TODO
            // .getPrincipals returns a Set, so ordering may not be ensured - not sure if it's worth
            // looking for a proper solution or move rather to GUMS for local grid user mapping ...
            // problem with different format of gridmapfiles:
            // "/DC=org/DC=doegrids/OU=People/CN=Zdenek Maxa 202285" "/cms/Role=cmsuser" uscms1713
            // "/DC=org/DC=doegrids/OU=People/CN=Zdenek Maxa 202285" uscms1713
            // not helping, still getting: LocalID:/cms/Role=cmsuser
            // actually the issue of having additional "/cms/Role=cmsuser" was fixed by Mike
            //      in a script generating these mappings ...
            Set<UserNamePrincipal> principals = peerSubject.getPrincipals(UserNamePrincipal.class);
            int last = principals.size();
            UserNamePrincipal up = (UserNamePrincipal) principals.toArray()[0];
            localUserName = up.getName();
            System.out.println("Authentication finished, LocalID:" + localUserName);
        }
        
        try
        {            
            ResponseMsg response;
            
            // create response for client
            response = new ResponseMsg("Authentication successful", localUserName, 0);
            OutputStream os = client.getOutputStream();
            ObjectOutputStream oos = new ObjectOutputStream(os);
            System.out.println("Sending response to client: " + response);
            oos.writeObject(response);
            oos.flush();
            oos.close();
            System.out.println("Communication finished, closed.");
        }
        catch(Throwable t)
        {
            String m = "Exception occured in AuthService, reason: " + t.getMessage();
            System.out.println(m);
            t.printStackTrace();
            try
            {
                ResponseMsg response = new ResponseMsg(m, localUserName, 1);
                OutputStream os = client.getOutputStream();
                ObjectOutputStream oos = new ObjectOutputStream(os);
                oos.writeObject(response);
                oos.flush();
                oos.close();
            }
            catch(Throwable tt)
            {
                tt.printStackTrace();
                // likely no way how to inform the remote AuthClient party
            }            
        }
        finally
        {
            // make the end of conversation with one AuthClient
            System.out.println("---------------------------------------------------------");
        }

    }

    
    
    public static void printUsage()
    {
        System.out.println("usage: -p <port>");
    }
    
    
    
    public static void main(String[] args) throws Exception
    {
        System.out.println("AuthService starting ...");
        
        Map<String, Object> argsMap = Utils.parseArguments(args, Config.SINGLE_CMDLINE_ARGS);
        
        if(argsMap.get("-p") == null)
        {
            printUsage();
            throw new IllegalArgumentException("No port specified, exit.");
        }

        // if defined, redirect the stdout, stderr into a file
        // the chances are that the log output into this file may get messy
        // logging concurrently from multiple clients - yet to be studied in production
        // (esp. when autoFlush is on ...)
        PrintStream logStream = null;
        if(argsMap.get("-log") != null)
        {
            String logFileName = (String) argsMap.get("-log");
            System.out.println("Redirecting stdout, stderr into \"" + logFileName + "\"");
            
            FileOutputStream fos = new FileOutputStream(logFileName, true); // append boolean flag
            logStream = new PrintStream(fos, true); // autoFlush boolean flag - flush on newline
            
            System.setOut(logStream);
            System.setErr(logStream);
            
            System.out.println("=========================================================");
            System.out.println("AuthService starting (stdout, stderr redirected here) ...");
        }
        
        int port = Integer.valueOf((String) argsMap.get("-p"));
        AuthService service = new AuthService(port);
        service.start();
        
        System.out.println("AuthService started.");
        
        // gets here immediately, runs in a thread
        
        // install JVM shutdown hook to perform clean-up actions
        CleanupShutdownHook hook = new CleanupShutdownHook(service, logStream);
        Runtime.getRuntime().addShutdownHook(hook);
    }
}


/**
 * ShutDownHook is called during JVM shutdown, when application receives
 * terminating signal or on user's ctrl-c. (15 - SIGTERM)
 * 
 * This ShutdownHook cleans up the temporary / runtime data directory so that
 * another user could start the broker without getting permission denied
 * when broker tries to create runtime/temporary data directory. 
 */
class CleanupShutdownHook extends Thread
{
    private AuthService authService = null;
    private PrintStream logStream = null;
    
    public CleanupShutdownHook(AuthService service, PrintStream logStream)
    {
        authService = service;
        this.logStream = logStream;
        System.out.println("AuthService shutdown hook initialised.");
    }
    
    
    private void stopService()
    {
        System.out.println("Stopping the AuthService ...");
        
        try
        {
            authService.stopService();
            System.out.println("AuthService stopped.");
        }
        catch(Throwable t)
        {
            System.out.println("Could not stop AuthService, reason: " + t.getMessage());
        }
        System.out.flush();
        System.err.flush();
        if(logStream != null)
        {
            logStream.flush();
            logStream.close();
        }
        Runtime.getRuntime().exit(0); 
    }
        
        
        
    public void run()
    {
        System.out.println("AuthService shutdown hook called.");
        stopService();
    }      
}