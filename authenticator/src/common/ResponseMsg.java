package authenticator.common;

import java.io.Serializable;


public class ResponseMsg implements Serializable
{
    private String msg = null;
    private int statusCode = Integer.MIN_VALUE;
    private String localUserName = null;

    
    
    public ResponseMsg(String msg, String localUserName, int statusCode)
    {
        this.msg = msg;
        this.localUserName = localUserName;
        this.statusCode = statusCode;
    }

    
    
    public int getStatusCode()
    {
        return this.statusCode; 
    }
    
    
    
    public String getLocalUserName()
    {
        return this.localUserName;
    }
    
    
    
    public String getMsg()
    {
        return this.msg;
    }
    
    
    
    public String toString()
    {
        return "ResponseMsg: status code: '" + this.statusCode + "' local Grid user: '" +
               this.localUserName + "' message: '" + this.msg + "'";  
    }
}