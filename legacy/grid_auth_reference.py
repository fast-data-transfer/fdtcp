# code saved for future reference
# code taken from COMP stuff within CMSSW
# esp. grid - authentication stuff

# PRODCOMMON/src/python/ProdCommon/BossLite/Common/System.py
from subprocess import Popen, PIPE, STDOUT
import time
import os
import logging
import select, signal, fcntl


def setPgid():
    """
    preexec_fn for Popen to set subprocess pgid
    
    """

    os.setpgid( os.getpid(), 0 )


def executeCommand( command, timeout=None ):
    """
    _executeCommand_

    Util it execute the command provided in a popen object with a timeout
    """

    start = time.time()
    p = Popen( command, shell=True, \
               stdin=PIPE, stdout=PIPE, stderr=STDOUT, \
               close_fds=True, preexec_fn=setPgid )

    # playing with fd
    fd = p.stdout.fileno()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    # return values
    timedOut = False
    outc = []

    while 1:
        (r, w, e) = select.select([fd], [], [], timeout)

        if fd not in r :
            timedOut = True
            break

        read = p.stdout.read()
        if read != '' :
            outc.append( read )
        else :
            break

    if timedOut :
        stop = time.time()
        try:
            os.killpg( os.getpgid(p.pid), signal.SIGTERM)
            os.kill( p.pid, signal.SIGKILL)
            p.wait()
            p.stdout.close()
        except OSError, err :
            logging.warning(
                'Warning: an error occurred killing subprocess [%s]' \
                % str(err) )

        raise TimeOut( command, ''.join(outc), timeout, start, stop )


    try:
        p.wait()
        p.stdout.close()
    except OSError, err:
        logging.warning( 'Warning: an error occurred closing subprocess [%s] %s  %s' \
                         % (str(err), ''.join(outc), p.returncode ))

    returncode = p.returncode
    if returncode is None :
        returncode = -666666

    return ''.join(outc), returncode




# PRODCOMMON/src/python/ProdCommon/Credential/Proxy.py
# minor modifications: import -> used executeCommand functions
import os,sys
import commands
import traceback
import time
import re
import logging
#from ProdCommon.BossLite.Common.System import executeCommand
try:
    from hashlib import sha1
except:
    from sha import sha as sha1 

class Proxy:
    """
    basic class to handle user Token
    """
    def __init__( self, **args ):
        self.timeout = args.get( "timeout", None )
        self.myproxyServer = args.get( "myProxySvr", '')
        self.serverDN = args.get( "serverDN", '')
        self.shareDir = args.get( "shareDir", '')
        self.userName = args.get( "userName", '')
        self.debug = args.get("debug",False)
        self.logging = args.get( "logger", logging )

        self.args = args

    def ExecuteCommand( self, command ):
        """
        _ExecuteCommand_

        Util it execute the command provided in a popen object with a timeout
        """

        return executeCommand( command, self.timeout )


    def getUserProxy(self):
        """
        """
        proxy = None
        if os.environ.has_key('X509_USER_PROXY'):
            proxy = os.environ['X509_USER_PROXY']
        else:
            proxy = '/tmp/x509up_u'+str(os.getuid())

        return proxy.strip()

    def getSubject(self, proxy = None):
        """
        """
        subject = None
        if proxy == None: proxy=self.getUserProxy()

        cmd = 'openssl x509 -in '+proxy+' -subject -noout'

        out, ret = self.ExecuteCommand(cmd)
        if ret != 0 :
            msg = "Error while checking proxy subject for %s"%proxy
            raise Exception(msg)

        subjList = []
        for s in out.split('/'):
            if 'subject' in s: continue
            if 'proxy' in s: continue
            subjList.append(s)

        subject = '/' + '/'.join(subjList)
        return subject.strip()

    def getUserName(self, proxy = None ):
        """
        """
        uName = None
        if proxy == None: proxy=self.getUserProxy()

        cmd = "voms-proxy-info -file "+proxy+" -subject"

        out, ret = self.ExecuteCommand(cmd)
        if ret != 0 :
            msg = "Error while extracting User Name from proxy %s"%proxy
            raise Exception(msg)

        uName = ''
        for cname in out.split('/'):
            if cname[:3] == "CN=" and cname[3:].find('proxy') == -1:
                if len(cname[3:]) > len(uName):
                    uName = cname[3:]

        return uName.strip()

    def getTimeLeft(self, proxy = None ):
        """
        """
        if proxy == None: proxy=self.getUserProxy()
        if not os.path.exists(proxy):
            return 0

        cmd = 'voms-proxy-info -file '+proxy+' -timeleft 2>/dev/null'

        timeLeftLocal,  ret = self.ExecuteCommand(cmd)

        if ret != 0 and ret != 1:
            msg = "Error while checking proxy timeleft for %s"%proxy
            raise Exception(msg)

        result = -1
        try:
            result = int(timeLeftLocal)
        except Exception:
            result = 0
        if result > 0:
            ACTimeLeftLocal = self.getVomsLife(proxy)
            if ACTimeLeftLocal > 0:
                result = self.checkLifeTimes(int(timeLeftLocal), ACTimeLeftLocal, proxy)
            else:
                result = 0
        return result

    def checkLifeTimes(self, ProxyLife, VomsLife, proxy):
        """
        """
        if abs(ProxyLife - VomsLife) > 900 :
            h=int(ProxyLife)/3600
            m=(int(ProxyLife)-h*3600)/60
            proxyLife="%d:%02d" % (h,m)
            h=int(VomsLife)/3600
            m=(int(VomsLife)-h*3600)/60
            vomsLife="%d:%02d" % (h,m)
            msg =  "proxy lifetime %s is different from voms extension lifetime%s for proxy %s\n CRAB will ask ask you create a new proxy" % (proxyLife, vomsLife, proxy)
            self.logging.info(msg)
            result = 0
        else:
            result = ProxyLife
        return result

    def getVomsLife(self, proxy):
        """
        """
        cmd = 'voms-proxy-info -file '+proxy+' -actimeleft 2>/dev/null'

        ACtimeLeftLocal,  ret = self.ExecuteCommand(cmd)

        if ret != 0 and ret != 1:
            msg = "Error while checking proxy actimeleft for %s"%proxy
            raise Exception(msg)

        result = -1
        try:
            result = int(ACtimeLeftLocal)
        except Exception:
            msg  =  "voms extension lifetime for proxy %s is 0 \n"%proxy
            msg +=  "\tCRAB will ask ask you create a new proxy"
            self.logging.info(msg)
            result = 0
        return result

    def renewCredential( self, proxy=None ):
        """
        """
        if proxy == None: proxy=self.getUserProxy()
        # check
        if not self.checkCredential():
            # ask for proxy delegation
            # using myproxy
            pass
        return

    def checkAttribute( self, proxy=None, vo='cms', group=None, role=None):
        """
        """
        valid = True
        if proxy == None: proxy=self.getUserProxy()

        ## check first attribute
        cmd = 'export X509_USER_PROXY=%s; voms-proxy-info -fqan 2>/dev/null | head -1'%proxy

        reg="/%s/"%vo
        if group:
            reg+=group
            if role: reg+="/Role=%s"%role
        else:
            if role: reg+="Role=%s"%role

        att, ret = self.ExecuteCommand(cmd)

        if ret != 0 :
            msg = "Error while checking attribute for %s"%proxy
            raise Exception(msg)

       ## you always have at least  /cms/Role=NULL/Capability=NULL
        if not re.compile(r"^"+reg).search(att):
            self.logging.info("Wrong VO group/role.")
            valid = False
        return valid

    def ManualRenewCredential( self, proxy=None, vo='cms', group=None, role=None ):
        """
        """
        cmd = 'voms-proxy-init -voms %s'%vo

        if group:
            cmd += ':/'+vo+'/'+group
            if role: cmd += '/Role='+role
        else:
            if role: cmd += ':/'+vo+'/Role='+role

        cmd += ' -valid 192:00'
        try:
            out = os.system(cmd)
            if (out>0): raise Exception("Unable to create a valid proxy!\n")
        except:
            msg = "Unable to create a valid proxy!\n"
            raise Exception(msg)

    def destroyCredential(self, proxy):
        """
        """
        if proxy == None:
            msg = "Error no valid proxy to remove "
            raise Exception(msg)
        cmd = '[ -e %s ] && rm %s'%(proxy, proxy)

        out, ret = self.ExecuteCommand(cmd)
        if ret != 0 :
            msg = "Error while removing proxy %s"%proxy
            raise Exception(msg)

        return

    def checkMyProxy( self , proxy=None, Time=4, checkRetrieverRenewer=False):
        """
        """
        if proxy == None: proxy=self.getUserProxy()
        ## check the myproxy server
        valid = True

        #cmd = 'export X509_USER_PROXY=%s; myproxy-info -d -s %s 2>/dev/null'%(proxy,self.myproxyServer)
        cmd = 'myproxy-info -d -s %s 2>/dev/null'%(self.myproxyServer)

        out, ret = self.ExecuteCommand(cmd)
        if ret != 0 and ret != 1 :
            msg = "Error while checking myproxy timeleft for %s"%proxy
            raise Exception(msg)

        if not out:
            self.logging.info('No credential delegated to myproxy server %s .'%self.myproxyServer)
            valid = False
        else:

            ## minimum time: 4 days
            minTime = int(Time) * 24 * 3600
            ## regex to extract the right information
            timeleftList = re.compile("timeleft: (?P<hours>[\\d]*):(?P<minutes>[\\d]*):(?P<seconds>[\\d]*)").findall(out)

            ## the first time refers to the flat user proxy, the other ones are related to the server credential name
            try:
                hours, minutes, seconds = timeleftList[0]
                timeleft = int(hours)*3600 + int(minutes)*60 + int(seconds)
            except Exception, e:
                self.logging.info('Error extracting timeleft from proxy')
                self.logging.debug( str(e) )
                valid = False
            if timeleft < minTime:
                self.logging.info('Your proxy will expire in:\n\t%s hours %s minutes %s seconds\n'%(hours,minutes,seconds))
                valid = False

            # check the timeleft for the required server
            if checkRetrieverRenewer and len(self.serverDN.strip()) > 0:
                serverCredName = sha1(self.serverDN).hexdigest()
                credNameList = re.compile(" name: (?P<CN>.*)").findall(out)
                credTimeleftList = timeleftList[1:]

                # check if the server credential exists
                if serverCredName not in credNameList :
                    self.logging.info('Your proxy lacks of retrieval and renewal policies for the requested server.')
                    self.logging.info('Renew your myproxy credentials.')
                    valid = False
                    return valid

                try:
                    hours, minutes, seconds = credTimeleftList[ credNameList.index(serverCredName) ]
                    timeleft = int(hours)*3600 + int(minutes)*60 + int(seconds)
                except Exception, e:
                    self.logging.info('Error extracting timeleft from credential name')
                    self.logging.debug( str(e) )
                    valid = False
                if timeleft < minTime:
                    logMsg  = 'Your credential for the required server will expire in:\n\t'
                    logMsg += '%s hours %s minutes %s seconds\n'%(hours,minutes,seconds)
                    self.logging.info(logMsg)
                    valid = False

                # clean up expired credentials for other servers
                cleanCredCmdList = []
                for credIdx in xrange(len(credNameList)):
                    hours, minutes, seconds = credTimeleftList[ credIdx ]
                    timeleft = int(hours)*3600 + int(minutes)*60 + int(seconds)
                    if timeleft == 0:
                        cleanupCmd = "myproxy-destroy -d -k %s"%(credNameList[credIdx]) 
                        cleanCredCmdList.append( cleanupCmd )  
                    pass

                cleanCredCmd = " && ".join(cleanCredCmdList)
                if len(cleanCredCmd)>0:
                    self.logging.debug('Removing expired credentials: %s'%cleanCredCmd) 
                    try:
                        out, ret = self.ExecuteCommand( cleanCredCmd )
                    except:
                        self.logging.debug('Error in cleaning expired credentials. Ignore and go ahead.')
                        pass
                   
        return valid

    def ManualRenewMyProxy( self ):
        """
        """
        cmd = 'myproxy-init -d -n -s %s'%self.myproxyServer

        if len( self.serverDN.strip() ) > 0:
            credName = sha1(self.serverDN).hexdigest()
            cmd += ' -x -R \'%s\' -Z \'%s\' -k %s -t 168:00 '%(self.serverDN, self.serverDN, credName)

        out = os.system(cmd)
        self.logging.debug('MyProxy delegation:\n%s'%cmd)
        if (out>0):
            raise Exception("Unable to delegate the proxy to myproxyserver %s !\n" % self.myproxyServer )
        return

    def logonMyProxy( self, proxyCache, userDN, vo='cms', group=None, role=None):
        """
        """
        proxyFilename= os.path.join(proxyCache, sha1(userDN).hexdigest() )

        # myproxy-logon -d -n -s $MYPROXY_SERVER -o <outputFile> -l <userDN> -k <credName>

        # compose the VO attriutes
        voAttr = vo
        if group:
            voAttr += ':/'+vo+'/'+group
            if role: voAttr += '/Role='+role
        else:
            if role: voAttr += ':/'+vo+'/Role='+role

        # get the credential name for this retriever
        credName = sha1( self.getSubject('$HOME/.globus/hostcert.pem') ).hexdigest()

        # compose the delegation or renewal commands with the regeneration of Voms extensions
        cmdList = []
        cmdList.append('unset X509_USER_CERT X509_USER_KEY')
        cmdList.append('&& env')
        cmdList.append('X509_USER_CERT=$HOME/.globus/hostcert.pem')
        cmdList.append('X509_USER_KEY=$HOME/.globus/hostkey.pem')

        ## get a new delegated proxy
        cmdList.append('myproxy-logon -d -n -s %s -o %s -l \'%s\' -k %s -t 168:00'%\
            (self.myproxyServer, proxyFilename, userDN, credName) )

        cmd = ' '.join(cmdList)
        msg, out = self.ExecuteCommand(cmd)

        self.logging.debug('MyProxy logon - retrieval:\n%s'%cmd)
        if (out>0):
            self.logging.debug('MyProxy result - retrieval :\n%s'%msg)
            raise Exception("Unable to retrieve delegated proxy for user DN %s! Exit code:%s"%(userDN, out) )

        self.vomsExtensionRenewal(proxyFilename, voAttr)

        return proxyFilename

    def renewalMyProxy(self, proxyFilename):
        """
        """

        # get vo, group and role from the current certificate
        cmd = 'env X509_USER_PROXY=%s voms-proxy-info -vo 2>/dev/null | head -1'%proxyFilename
        att, ret = self.ExecuteCommand(cmd)
        if ret != 0:
            raise Exception("Unable to get VO for proxy %s! Exit code:%s"%(proxyFilename, ret) )
        vo = att.replace('\n','')

        # at least /cms/Role=NULL/Capability=NULL
        cmd = 'env X509_USER_PROXY=%s voms-proxy-info -fqan 2>/dev/null | head -1'%proxyFilename
        att, ret = self.ExecuteCommand(cmd)
        if ret != 0:
            raise Exception("Unable to get FQAN for proxy %s! Exit code:%s"%(proxyFilename, ret) )

        # prepare the attributes
        att = att.split('\n')[0]
        att = att.replace('/Role=NULL','')
        att = att.replace('/Capability=NULL','')

        voAttr = vo + ':' + att

        # get the credential name for this renewer
        credName = sha1( self.getSubject('$HOME/.globus/hostcert.pem') ).hexdigest()

        # renew the certificate
        # compose the delegation or renewal commands with the regeneration of Voms extensions
        cmdList = []
        cmdList.append('unset X509_USER_CERT X509_USER_KEY')
        cmdList.append('&& env')
        cmdList.append('X509_USER_CERT=$HOME/.globus/hostcert.pem')
        cmdList.append('X509_USER_KEY=$HOME/.globus/hostkey.pem')

        ## refresh an existing proxy
        cmdList.append('myproxy-logon -d -n -s %s -a %s -o %s -k %s -t 168:00'%\
            (self.myproxyServer, proxyFilename, proxyFilename, credName) )

        cmd = ' '.join(cmdList)
        msg, out = self.ExecuteCommand(cmd)
        self.logging.debug('MyProxy renewal - logon :\n%s'%cmd)
        if (out>0):
            self.logging.debug('MyProxy renewal - logon result:\n%s'%msg)
            raise Exception("Unable to retrieve proxy for renewal: %s! Exit code:%s"%(proxyFilename, out) )

        self.vomsExtensionRenewal(proxyFilename, voAttr)

        return

    def vomsExtensionRenewal(self, proxy, voAttr='cms'):
        ## get validity time for retrieved flat proxy
        cmd = 'grid-proxy-info -file '+proxy+' -timeleft 2>/dev/null'

        timeLeft,  ret = self.ExecuteCommand(cmd)
        if ret != 0 and ret != 1:
            raise Exception("Error while checking retrieved proxy timeleft for %s"%proxy )

        try:
            timeLeft = int(timeLeft) - 60
        except Exception:
            timeLeft = 0

        self.logging.debug( 'Timeleft for retrieved proxy: (exit code %s) %s'%(ret, timeLeft) )

        if timeLeft <= 0:
            # fake value, it would fail in any case
            vomsValid = "12:00"
        else:
            vomsValid = "%d:%02d"%( timeLeft/3600, (timeLeft-(timeLeft/3600)*3600)/60 )

        self.logging.debug( 'Requested voms validity: %s'%vomsValid )

        ## set environ and add voms extensions
        cmdList = []
        cmdList.append('env')
        cmdList.append('X509_USER_CERT=%s'%proxy)
        cmdList.append('X509_USER_KEY=%s'%proxy)
        cmdList.append('voms-proxy-init -noregen -voms %s -cert %s -key %s -out %s -bits 1024 -valid %s'%\
             (voAttr, proxy, proxy, proxy, vomsValid) )

        cmd = ' '.join(cmdList)
        msg, out = self.ExecuteCommand(cmd)
        self.logging.debug('Voms extension:\n%s'%cmd)
        if (out>0):
            self.logging.debug('Voms extension result:\n%s'%msg)
            raise Exception("Unable to renew proxy voms extension: %s! Exit code:%s"%(proxy, out) )

        return
    
    




# mapping grid user to local user using gridmapfile (static files)
# code extracted from pyGridWare-1.4.0
# codes modified to remove references to twisted, zope
# using code pyGridWare/security/authz/interfaces.py (incomplete)
from common.cmscomp import Proxy

gridMapFile = "security/cms-grid-mapfile"
userGridProxy = "security/x509up_u2574"


class GridUserMappingException(Exception):
    pass


# taken from pyGridWare/security/authz/checkers.py
class GridMapChecker(object):
    """takes an X509Credential, uses the SubjectDN to perform
    a lookup on a grid-mapfile dict.  Using this checker limits
    an implementation to utilizing one GridMap.  You could change
    the gridmap file, but all GridMapCheckers would use the same
    one.
    
    returns the userID.
    
    class attributes:
        gridmapfile -- gridmap file
        interval -- interval for refreshing gridmap dict
        gridmap -- gridmap dictionary of subjectDN to user mapping.
    """
    
    
    def __init__(self, gridMapFile):
        GridMapChecker.load(gridMapFile)
        
        
    @classmethod
    def load(cls, gridMapFile):
        """gridmapfile will only be loaded when creating instance of GridMapChecker.
           this has to be address by background periodic loading, or ...
        """
        fd = open(gridMapFile , 'r')
        
        # actual map is only held with the class, not instances
        # doesn't work
        #cls.gridMap = dict(map(lambda s: s.strip('"').split('" ')[:2], fd))
        cls.gridMap = dict()
        for line in fd.readlines():
            # line:
            # "/C=AT/O=AustrianGrid/OU=OEAW/OU=oeaw-vienna/CN=Christian Thomay" uscms1768"
            line = line.strip()
            try:
                l = line.split('"')[1:] # not interested in the first empty string
                # TODO
                # improve
                cls.gridMap[l[0].strip()] = l[1].strip()
            except IndexError:
                pass # probably some comment in the file ...
            
        #print "gridmap:\n%s", cls.gridMap
        
        
        
    def requestLocalId(self, subject):
        # see original method code ...
        # need to get subject, from pyGridWare its not clear
        # what happens - relevant method get_subject at 
        # IX509Credential(Interface) is empty ...
        # so, doesn't seem be actually implemented in pyGridWare, could
        # also just be wrapper around external openssl call like CRAB/ProdAgent does
        #subject =  credentials.get_subject()
        
        # openssl x509 -in '+proxy+' -subject -noout
        
        if not self.gridMap.has_key(subject):
            #form Subject DNs by removing the last CN field in the
            #subject, continue this until subject name matches or 
            #there are no more CN fields
            while True:
                subject_name_list = subject.split("/")
                subject_name_list.pop()
                subject_name_list.pop(0)
                new_subject_list = map(lambda x: "/" +x,subject_name_list)
                subject = "".join(new_subject_list)
                if self.gridMap.has_key(subject):
                    break
                try:
                    subject.index("CN")
                except ValueError:
                    m = "authentication failed, no gridmap entry for subjectDN '%s'" % subject
                    GridUserMappingException(m)
            else:
                m = "authentication failed, no gridmap entry for subjectDN '%s'" % subject
                GridUserMappingException(m)

            
        #TODO: should probably check if user exists?
        user = self.gridMap.get(subject)
        if not user:
            m = "authentication failed, bad gridmap entry for subjectDN '%s'" % subject
            GridUserMappingException(m)
        else:
            print ("mapping match found: subject: '%s' gridmapfile user: '%s'" %
                   (subject, user)) 
        return user
        
        
    # leave it here for reference
#    def requestAvatarId(self, credentials):
#        """return subject DN
#        """
#        if self.gridmap is None:
#            defer.fail(UnauthorizedLogin(
#                           "permission denied: no gridmap-file"))
#            
#        subject =  credentials.get_subject()
#        log.msg('gridmap subject "%s"', subject, debug=True)
#        if not subject:
#            defer.fail(UnauthorizedLogin('permission denied: "%s" no gridmap entry'))
#            
#        if not self.gridmap.has_key(subject):
#            #form Subject DNs by removing the last CN field in the
#            #subject, continue this until subject name matches or 
#            #there are no more CN fields
#            while True:
#                subject_name_list = subject.split("/")
#                subject_name_list.pop()
#                subject_name_list.pop(0)
#                new_subject_list = map(lambda x: "/" +x,subject_name_list)
#                subject = "".join(new_subject_list)
#                if self.gridmap.has_key(subject):
#                    break
#                try:
#                    subject.index("CN")
#                except ValueError:
#                    defer.fail(UnauthorizedLogin(
#                       'authentication failed, no gridmap entry for subjectDN "%s"' %
#                       subject))
#            else:
#                defer.fail(UnauthorizedLogin(
#                   'authentication failed, no gridmap entry for subjectDN "%s"' %
#                   subject))
#            
#        #TODO: should probably check if user exists?
#        user = self.gridmap.get(subject)
#        if not user:
#            defer.fail(UnauthorizedLogin(
#               'authentication failed, bad gridmap entry for subjectDN "%s"' %
#               subject))
#            
#        return defer.succeed(user)


def gridLocalUserMapping():
    global gridMapFile, userGridProxy
    
    print ("searching local user mapping based on grid proxy '%s' consulting "
           "gridmapfile '%s'" % (userGridProxy, gridMapFile))
    
    checker = GridMapChecker(gridMapFile)
    # Proxy will later be an instance with attributes properly set
    proxy = Proxy() # create an empty one
    # calls external openssl program ...
    subject = proxy.getSubject(userGridProxy)
    print "proxy subject: '%s'" % subject
    localUser = checker.requestLocalId(subject)
    print "local user: '%s'" % localUser
    
    print "\n\n\n"
    from M2Crypto.X509 import load_cert
    cert = load_cert("pyro-ssl-example/certs/server.crt")
    print "subject read by M2Crypto: '%s'" % cert.get_subject()
    
    cert = load_cert(userGridProxy)
    print "subject read by M2Crypto: '%s'" % cert.get_subject()
