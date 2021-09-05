#!/usr/bin/python
import sys, os.path, time, stat, socket, base64,json
import configparser
import shutil
import yapl.Utilities as Utilities
from subprocess import call,check_output, check_call, CalledProcessError, Popen, PIPE
from os import chmod, environ
from yapl.Trace import Trace, Level
from yapl.Exceptions import MissingArgumentException

TR = Trace(__name__)
StackParameters = {}
StackParameterNames = []
class CPDInstall(object):
    ArgsSignature = {
                    '--region': 'string',
                    '--stack-name': 'string',
                    '--stackid': 'string',
                    '--logfile': 'string',
                    '--loglevel': 'string',
                    '--trace': 'string'
                   }

    def __init__(self):
        """
        Constructor

        NOTE: Some instance variable initialization happens in self._init() which is 
        invoked early in main() at some point after _getStackParameters().
        """
        object.__init__(self)
        self.home = os.path.expanduser("/ibm")
        self.logsHome = os.path.join(self.home,"logs")
         
    #endDef 
    def _getArg(self,synonyms,args,default=None):
        """
        Return the value from the args dictionary that may be specified with any of the
        argument names in the list of synonyms.

        The synonyms argument may be a Jython list of strings or it may be a string representation
        of a list of names with a comma or space separating each name.

        The args is a dictionary with the keyword value pairs that are the arguments
        that may have one of the names in the synonyms list.

        If the args dictionary does not include the option that may be named by any
        of the given synonyms then the given default value is returned.

        NOTE: This method has to be careful to make explicit checks for value being None
        rather than something that is just logically false.  If value gets assigned 0 from
        the get on the args (command line args) dictionary, that appears as false in a
        condition expression.  However 0 may be a legitimate value for an input parameter
        in the args dictionary.  We need to break out of the loop that is checking synonyms
        as well as avoid assigning the default value if 0 is the value provided in the
        args dictionary.
        """
        
        value = None
        if (type(synonyms) != type([])):
            synonyms = Utilities.splitString(synonyms)
        #endIf

        for name in synonyms:
            value = args.get(name)
            if (value != None):
                break
        #endIf
        #endFor

        if (value == None and default != None):
         value = default
        #endIf

        return value
    #endDef

    def _configureTraceAndLogging(self,traceArgs):
        """
        Return a tuple with the trace spec and logFile if trace is set based on given traceArgs.

        traceArgs is a dictionary with the trace configuration specified.
            loglevel|trace <tracespec>
            logfile|logFile <pathname>

        If trace is specified in the trace arguments then set up the trace.
        If a log file is specified, then set up the log file as well.
        If trace is specified and no log file is specified, then the log file is
        set to "trace.log" in the current working directory.
        """
        logFile = self._getArg(['logFile','logfile'], traceArgs)
        if (logFile):
            TR.appendTraceLog(logFile)
        #endIf

        trace = self._getArg(['trace', 'loglevel'], traceArgs)

        if (trace):
            if (not logFile):
                TR.appendTraceLog('trace.log')
            #endDef

        TR.configureTrace(trace)
        #endIf
        return (trace,logFile)
    #endDef
   
 
    def installCPD(self,icpdInstallLogFile):
        """
        creates a OC project with user defined name
        """

        methodName = "installCPD"
        os.chmod(self.installer_path,stat.S_IEXEC)
      
        try:
            oc_login = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
            retcode = call(oc_login,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Log in to OC with admin user %s"%retcode)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        if(self.installFoundationalService == "True"):
            TR.info(methodName, "Create namespaces for Foundational Services")
            oc_new_project ="oc new-project " + self.foundation_service_namespace
            try:
                retcode = call(oc_new_project,shell=True, stdout=icpdInstallLogFile)
                TR.info(methodName,"Create new project with user defined project name %s,retcode=%s" %(self.foundation_service_namespace,retcode))
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))  

            oc_new_project ="oc new-project " + self.cpd_operator_namespace
            try:
                retcode = call(oc_new_project,shell=True, stdout=icpdInstallLogFile)
                TR.info(methodName,"Create new project with user defined project name %s,retcode=%s" %(self.cpd_operator_namespace,retcode))
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

            self.createOperatorGroups(self, icpdInstallLogFile)

        if(self.installCPDControlPlane == "True"):
            oc_new_project ="oc new-project " + self.cpd_instance_namespace
            try:
                retcode = call(oc_new_project,shell=True, stdout=icpdInstallLogFile)
                TR.info(methodName,"Create new project with user defined project name %s,retcode=%s" %(self.cpd_instance_namespace,retcode))
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))      
            
            self.createNamespaceScope()

        litestart = Utilities.currentTimeMillis()
        TR.info(methodName,"Start installing Lite package")
        self.installAssembliesAirgap("lite",self.default_load_from,icpdInstallLogFile)
        liteend = Utilities.currentTimeMillis()
        self.printTime(litestart, liteend, "Installing Lite")

        get_cpd_route_cmd = "oc get route -n "+self.namespace+ " | grep '"+self.namespace+"' | awk '{print $2}'"
        TR.info(methodName, "Get CPD URL")
        try:
            self.cpdURL = check_output(['bash','-c', get_cpd_route_cmd]) 
            TR.info(methodName, "CPD URL retrieved %s"%self.cpdURL)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        if(self.installWSL == "True"):
            TR.info(methodName,"Start installing WSL package")
            wslstart = Utilities.currentTimeMillis()
            if(self.installWSL_load_from == "NA"):
                self.installAssembliesAirgap("wsl",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("wsl",self.installWSL_load_from,icpdInstallLogFile)
            wslend = Utilities.currentTimeMillis()
            TR.info(methodName,"WSL package installation completed")
            self.printTime(wslstart, wslend, "Installing WSL")
        
        if(self.installWML == "True"):
            TR.info(methodName,"Start installing WML package")
            wmlstart = Utilities.currentTimeMillis()
            if(self.installWML_load_from == "NA"):
                self.installAssembliesAirgap("wml",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("wml",self.installWML_load_from,icpdInstallLogFile)
            wmlend = Utilities.currentTimeMillis()
            TR.info(methodName,"WML package installation completed")
            self.printTime(wmlstart, wmlend, "Installing WML")

        if(self.installOSWML == "True"):
            TR.info(methodName,"Start installing AI Openscale package")
            aiostart = Utilities.currentTimeMillis()
            if(self.installOSWML_load_from == "NA"):
                self.installAssembliesAirgap("aiopenscale",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("aiopenscale",self.installOSWML_load_from,icpdInstallLogFile)
            aioend = Utilities.currentTimeMillis()
            TR.info(methodName,"AI Openscale package installation completed")
            self.printTime(aiostart, aioend, "Installing AI Openscale")    

        if(self.installCDE == "True"):
            TR.info(methodName,"Start installing Cognos Dashboard package")
            cdestart = Utilities.currentTimeMillis()
            if(self.installCDE_load_from == "NA"):
                self.installAssembliesAirgap("cde",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("cde",self.installCDE_load_from,icpdInstallLogFile)
            cdeend = Utilities.currentTimeMillis()
            TR.info(methodName,"Cognos Dashboard package installation completed")
            self.printTime(cdestart, cdeend, "Installing Cognos Dashboard")  

        
        if(self.installRStudio == "True"):
            TR.info(methodName,"Start installing RStudio package")
            rstudiostart = Utilities.currentTimeMillis()
            if(self.installRStudio_load_from == "NA"):
                self.installAssembliesAirgap("rstudio",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("rstudio",self.installRStudio_load_from,icpdInstallLogFile)
            rstudioend = Utilities.currentTimeMillis()
            TR.info(methodName,"RStudio package installation completed")
            self.printTime(rstudiostart, rstudioend, "Installing RStudio")      
        
        if(self.installSPSS == "True"):
            TR.info(methodName,"Start installing SPSS package")
            spssstart = Utilities.currentTimeMillis()
            if(self.installSPSS_load_from == "NA"):
                self.installAssembliesAirgap("spss-modeler",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("spss-modeler",self.installSPSS_load_from,icpdInstallLogFile)
            spssend = Utilities.currentTimeMillis()
            TR.info(methodName,"SPSS package installation completed")
            self.printTime(spssstart, spssend, "Installing SPSS")

        if(self.installSpark == "True"):
            TR.info(methodName,"Start installing Spark AE package")
            sparkstart = Utilities.currentTimeMillis()
            if(self.installSpark_load_from == "NA"):
                self.installAssembliesAirgap("spark",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("spark",self.installSpark_load_from,icpdInstallLogFile)
            sparkend = Utilities.currentTimeMillis()
            TR.info(methodName,"Spark AE  package installation completed")
            self.printTime(sparkstart, sparkend, "Installing Spark AE")     

        if(self.installRuntimeGPUPy37 == "True"):
            TR.info(methodName,"Start installing GPUPy37 package")
            gpupy36start = Utilities.currentTimeMillis()
            if(self.installRuntimeGPUPy37_load_from == "NA"):
                self.installAssembliesAirgap("runtime-addon-py37gpu",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("runtime-addon-py37gpu",self.installRuntimeGPUPy37_load_from,icpdInstallLogFile)
            gpupy36end = Utilities.currentTimeMillis()
            TR.info(methodName,"GPUPy36 package installation completed")
            self.printTime(gpupy36start, gpupy36end, "Installing GPUPy36")
        
        if(self.installRuntimeR36 == "True"):
            TR.info(methodName,"Start installing RuntimeR36 package")
            r36start = Utilities.currentTimeMillis()
            if(self.installRuntimeR36_load_from == "NA"):
                self.installAssembliesAirgap("runtime-addon-py37gpu",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("runtime-addon-r36",self.installRuntimeR36_load_from,icpdInstallLogFile)
            r36end = Utilities.currentTimeMillis()
            TR.info(methodName,"R36 package installation completed")
            self.printTime(r36start, r36end, "Installing R36")
        
        if(self.installHEE == "True"):
            TR.info(methodName,"Start installing HEE package")
            heestart = Utilities.currentTimeMillis()
            if(self.installHEE_load_from == "NA"):
                self.installAssembliesAirgap("hadoop-addon",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("hadoop-addon",self.installHEE_load_from,icpdInstallLogFile)
            heeend = Utilities.currentTimeMillis()
            TR.info(methodName,"HEE package installation completed")
            self.printTime(heestart, heeend, "Installing HEE")
        
        if(self.installDODS == "True"):
            TR.info(methodName,"Start installing DODS package")
            dodsstart = Utilities.currentTimeMillis()
            if(self.installDODS_load_from == "NA"):
                self.installAssembliesAirgap("dods",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("dods",self.installDODS_load_from,icpdInstallLogFile)
            dodsend = Utilities.currentTimeMillis()
            TR.info(methodName,"DODS package installation completed")
            self.printTime(dodsstart, dodsend, "Installing DODS") 

        if(self.installWKC == "True"):
            TR.info(methodName,"Start installing WKC package")
            wkcstart = Utilities.currentTimeMillis()
            if(self.installWKC_load_from == "NA"):
                self.installAssembliesAirgap("wkc",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("wkc",self.installWKC_load_from,icpdInstallLogFile)            
            wkcend = Utilities.currentTimeMillis()
            TR.info(methodName,"WKC package installation completed")
            self.printTime(wkcstart, wkcend, "Installing WKC")
        
        if(self.installStreams == "True"):
            TR.info(methodName,"Start installing Streams package")
            streamsstart = Utilities.currentTimeMillis()
            if(self.installStreams_load_from == "NA"):
                self.installAssembliesAirgap("streams",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("streams",self.installStreams_load_from,icpdInstallLogFile)   
            streamssend = Utilities.currentTimeMillis()
            TR.info(methodName,"Streams package installation completed")
            self.printTime(streamsstart, streamsend, "Installing Streams")
            
        if(self.installDV == "True"):
            TR.info(methodName,"Start installing DV package")
            dvstart = Utilities.currentTimeMillis()
            if(self.installDV_load_from == "NA"):
                self.installAssembliesAirgap("dv",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("dv",self.installDV_load_from,icpdInstallLogFile)   
            dvend = Utilities.currentTimeMillis()
            TR.info(methodName,"DV package installation completed")
            self.printTime(dvstart, dvend, "Installing DV")      


        TR.info(methodName,"Installed all packages.")
    #endDef 

   
    def printTime(self, beginTime, endTime, text):
        """
        method to capture time elapsed for each event during installation
        """
        methodName = "printTime"
        elapsedTime = (endTime - beginTime)/1000
        etm, ets = divmod(elapsedTime,60)
        eth, etm = divmod(etm,60) 
        TR.info(methodName,"Elapsed time (hh:mm:ss): %d:%02d:%02d for %s" % (eth,etm,ets,text))
    #endDef

    def getToken(self,icpdInstallLogFile):
        """
        method to get sa token to be used to push and pull from local docker registry
        """
        methodName = "getToken"
        create_sa_cmd = "oc create serviceaccount cpdtoken"
        TR.info(methodName,"Create service account cpdtoken %s"%create_sa_cmd)
        try:
            retcode = call(create_sa_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Created service account cpdtoken %s"%retcode)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        addrole_cmd = "oc policy add-role-to-user admin system:serviceaccount:"+self.namespace+":cpdtoken"
        TR.info(methodName," Add role to service account %s"%addrole_cmd)
        try:
            retcode = call(addrole_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Role added to service account %s"%retcode)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        get_token_cmd = "oc serviceaccounts get-token cpdtoken"
        TR.info(methodName,"Retrieve token from service account %s"%get_token_cmd)
        return check_output(['bash','-c', get_token_cmd])
    #endDef  

    def changeNodeSettings(self, icpdInstallLogFile):
        methodName = "changeNodeSettings"
        TR.info(methodName,"  Start changing node settings of Openshift Container Platform")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        crio_conf   = "./templates/cpd/crio.conf"
        crio_mc     = "./templates/cpd/crio-mc.yaml"
        
        crio_config_data = base64.b64encode(self.readFileContent(crio_conf).encode('ascii')).decode("ascii")
        TR.info(methodName,"encode crio.conf to be base64 string")
        self.updateTemplateFile(crio_mc, '${crio-config-data}', crio_config_data)

        create_crio_mc  = "oc apply -f "+crio_mc

        TR.info(methodName,"Creating crio mc with command %s"%create_crio_mc)
        try:
            crio_retcode = check_output(['bash','-c', create_crio_mc]) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        TR.info(methodName,"Created Crio mc with command %s returned %s"%(create_crio_mc,crio_retcode))
        
        """
        "oc apply -f ${local.ocptemplates}/kernel-params_node-tuning-operator.yaml",
        "oc apply -f ${local.ocptemplates}/security-limits-mc.yaml",
        """
        setting_kernel_param_cmd =  "oc apply -f ./templates/cpd/kernel-params_node-tuning-operator.yaml"
        TR.info(methodName,"Create Node Tuning Operator for kernel parameter")
        try:
            retcode = check_output(['bash','-c', setting_kernel_param_cmd]) 
            TR.info(methodName,"Created Node Tuning Operator for kernel parameter %s" %retcode) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        db2_kubelet_config_cmd =  "oc apply -f ./templates/cpd/db2-kubelet-config-mc.yaml"
        TR.info(methodName,"Configure kubelet to allow Db2U to make syscalls as needed.")
        try:
            retcode = check_output(['bash','-c', db2_kubelet_config_cmd]) 
            TR.info(methodName,"Configured kubelet to allow Db2U to make syscalls %s" %retcode)  
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))  
        time.sleep(600)

        TR.info(methodName,"  Completed node settings of Openshift Container Platform")
    #endDef

    def configImagePull(self, icpdInstallLogFile):
        ##setup-global-pull-secret-bedrock.sh
        methodName = "configImagePull"
        TR.info(methodName,"  Start configuring image pull of Openshift Container Platform")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        set_global_pull_secret_command  = "./setup-global-pull-secret " + self.image_registry_url + " " + self.image_registry_user  + " " + self.image_registry_password

        TR.info(methodName,"Setting global pull secret with command %s"%set_global_pull_secret_command)
        try:
            crio_retcode = check_output(['bash','-c', set_global_pull_secret_command]) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        TR.info(methodName,"Setting global pull secret with command %s returned %s"%(create_crio_mc,crio_retcode))
        
        """
        "oc apply -f ${local.ocptemplates}/image_content_source_policy.yaml"
        """

        image_content_source_policy_template = "./templates/cpd/image_content_source_policy.yaml"
        TR.info(methodName,"Prepare for image content source policy")
        self.updateTemplateFile(image_content_source_policy_template, '${REPLACE_REGISTRY}', self.image_registry_url)
        

        image_content_source_policy_cmd =  "oc apply -f " + image_content_source_policy_template
        TR.info(methodName,"Create image content source policy")
        try:
            retcode = check_output(['bash','-c', image_content_source_policy_cmd]) 
            TR.info(methodName,"Create image content source policy %s" %retcode) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        time.sleep(900)

        TR.info(methodName,"  Completed image pull related setting")
    #endDef

    def createOperatorGroups(self, icpdInstallLogFile):
        methodName = "createOperatorGroups"
        TR.info(methodName,"  Create Operator Groups for BedRock and CPD Operators")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")
        
        """
        "oc apply -f bedrock-operator-group.yaml"
        """

        bedrock_operator_groups_template = "bedrock-operator-group.yaml"
        TR.info(methodName,"Prepare for bedrock operator groups")
        self.updateTemplateFile(bedrock_operator_groups_template, '${BEDROCK_NAMESPACE}', self.foundation_service_namespace)
        

        create_bedrock_operator_groups_cmd =  "oc apply -f " + bedrock_operator_groups_template
        TR.info(methodName,"Create bedrock operator groups")
        try:
            retcode = check_output(['bash','-c', create_bedrock_operator_groups_cmd]) 
            TR.info(methodName,"Create bedrock operator groups %s" %retcode) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))  

        """
        "oc apply -f cpd-operator-group.yaml"
        """

        cpd_operator_groups_template = "cpd-operator-group.yaml"
        TR.info(methodName,"Prepare for cpd operator groups")
        self.updateTemplateFile(cpd_operator_groups_template, '${CPD_OPERATORS_NAMESPACE}', self.cpd_operator_namespace)
        

        create_cpd_operator_groups_cmd =  "oc apply -f " + cpd_operator_groups_template
        TR.info(methodName,"Create cpd operator groups")
        try:
            retcode = check_output(['bash','-c', create_cpd_operator_groups_cmd]) 
            TR.info(methodName,"Create cpd operator groups %s" %retcode) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))  

        time.sleep(300)

        TR.info(methodName,"  Completed creating operator groups")
    #endDef

    def createNamespaceScope(self, icpdInstallLogFile):
        methodName = "createNamespaceScope"
        TR.info(methodName,"Create NamespaceScope for enabling the IBM Cloud Pak for Data platform operator to watch the project where you will install IBM Cloud Pak for Data")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")
        
        """
        "oc apply -f cpd-operators-namespace-scope.yaml"
        """

        cpd_operators_namespace_scope_template = "cpd-operators-namespace-scope.yaml"
        TR.info(methodName,"Prepare for creating NamespaceScope to watch the project where you will install IBM Cloud Pak for Data")
        self.updateTemplateFile(cpd_operators_namespace_scope_template, '${CPD_OPERATORS_NAMESPACE}', self.cpd_operator_namespace)

        self.updateTemplateFile(cpd_operators_namespace_scope_template, '${CPD_INSTANCE_NAMESPACE}', self.cpd_instance_namespace)

        create_cpd_operators_namespace_scope_cmd =  "oc apply -f " + cpd_operators_namespace_scope_template
        TR.info(methodName,"Create NamespaceScope to watch the project where you will install IBM Cloud Pak for Data")
        try:
            retcode = check_output(['bash','-c', create_cpd_operators_namespace_scope_cmd]) 
            TR.info(methodName,"Create NamespaceScope %s" %retcode) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output)) 

        time.sleep(300)

        TR.info(methodName,"  Completed creating NamespaceScope")
    #endDef

    def updateTemplateFile(self, source, placeHolder, value):
        """
        method to update placeholder values in templates
        """
        source_content = open(source).read()
        updated_source_content = source_content.replace(placeHolder, value)
        updated_file = open(source + ".gen", 'w')
        updated_file.write(updated_source_content)
        updated_file.close()
    #endDef    
    def readFileContent(self,source):
        file = open(source,mode='r')
        content = file.read()
        file.close()
        return content.rstrip()

    def installAssemblies(self, assembly, icpdInstallLogFile):
        """
        method to install assemlies
        for each assembly this method will execute adm command to apply all prerequistes
        Images will be pushed to local registry
        Installation will be done for the assembly using local registry
        """
        methodName = "installAssemblies"

        registry = self.regsitry.decode("ascii")+"/"+self.namespace
        apply_cmd = self.installer_path + " adm -r " + self.repo_path + " -a "+assembly+"  -n " + self.namespace+" --accept-all-licenses --apply | tee /ibm/logs/"+assembly+"_apply.log"
        TR.info(methodName,"Execute apply command for assembly %s"%apply_cmd)
        try:
            retcode = call(apply_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed apply command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

        #install
        TR.info("debug","self.storage_type= %s" %self.storage_type)
        TR.info("debug","self.storage_class= %s" %self.storage_class)
        
        if(self.storage_type == "portworx"):
            install_cmd = self.installer_path + " install --storageclass " + self.storage_class + " --override-config portworx -r " + self.repo_path + " --assembly "+assembly+" --arch x86_64 -n "+self.namespace+" --transfer-image-to "+registry+" --cluster-pull-username="+ self.ocp_admin_user + " --cluster-pull-password="+self.ocToken.decode("ascii")+" --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/"+self.namespace+" --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/" +assembly+"_install.log"
            install_cmd_for_print = install_cmd = self.installer_path + " install --storageclass " + self.storage_class + " --override-config portworx -r " + self.repo_path + " --assembly "+assembly+" --arch x86_64 -n "+self.namespace+" --transfer-image-to "+registry+" --cluster-pull-username="+ self.ocp_admin_user + " --cluster-pull-password="+base64.b64encode(self.ocToken).decode("ascii")+" --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/"+self.namespace+" --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/" +assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)    
        elif(self.storage_type == "ocs"):
            install_cmd = self.installer_path + " install --storageclass " + self.storage_class + " --override-config ocs -r " + self.repo_path + " --assembly "+assembly+" --arch x86_64 -n "+self.namespace+" --transfer-image-to "+registry+" --cluster-pull-username="+ self.ocp_admin_user + " --cluster-pull-password="+self.ocToken.decode("ascii")+" --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/"+self.namespace+" --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/" +assembly+"_install.log"
            install_cmd_for_print = self.installer_path + " install --storageclass " + self.storage_class + " --override-config ocs -r " + self.repo_path + " --assembly "+assembly+" --arch x86_64 -n "+self.namespace+" --transfer-image-to "+registry+" --cluster-pull-username="+ self.ocp_admin_user + " --cluster-pull-password="+base64.b64encode(self.ocToken).decode("ascii")+" --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/"+self.namespace+" --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/" +assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)
        elif(self.storage_type == "nfs"):
            install_cmd = self.installer_path + " install --storageclass " + self.storage_class + " -r " + self.repo_path + " --assembly "+assembly+" --arch x86_64 -n "+self.namespace+" --transfer-image-to "+registry+" --cluster-pull-username="+ self.ocp_admin_user + " --cluster-pull-password="+self.ocToken.decode("ascii")+" --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/"+self.namespace+" --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/" +assembly+"_install.log"
            install_cmd_for_print = self.installer_path + " install --storageclass " + self.storage_class + " -r " + self.repo_path + " --assembly "+assembly+" --arch x86_64 -n "+self.namespace+" --transfer-image-to "+registry+" --cluster-pull-username="+ self.ocp_admin_user + " --cluster-pull-password="+base64.b64encode(self.ocToken).decode("ascii")+" --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/"+self.namespace+" --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/" +assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)
        else:
            TR.error(methodName,"Invalid storage type : %s"%self.storage_type)

        try:     
            retcode = call(install_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Execute install command for assembly %s returned %s"%(assembly,retcode))  
        except CalledProcessError as e:
            TR.error(methodName,"Exception while installing service %s with message %s" %(assembly,e))
            self.rc = 1
    #endDef

    def installCatalogSourceAirgap(self, assembly, caseName, inventoryName, icpdInstallLogFile):
        """
        method to install Catalog Source

        """
        methodName = "installCatalogSourceAirgap"
  
        #Create the catalog source

        catalog_source_creation_cmd = self.installer_path + " case launch --case " + self.offline_dir_path + "/" + self.caseName + " --inventory " + inventoryName + " --namespace openshift-marketplace --action install-catalog --args \"--registry " + self.image_registry_url + " --inputDir " + self.offline_dir_path + " --recursive\""

        TR.info(methodName,"Execute catalog source creation command for %s"%assembly)
        try:
            retcode = call(catalog_source_creation_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Execute catalog source creation command for %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
            self.rc = 1
        
        time.sleep(300)

        #Status check to be addeded here
    #endDef

    def createOperatorSubscription(self, assembly, icpdInstallLogFile):

        methodName = "createOperatorSubscription"
        TR.info(methodName,"Start creating Operator Subscription")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        if(assembly == "Bedrock"):
            operator_sub_file = "bedrock-sub.yaml"
            self.updateTemplateFile(operator_sub_file, '${FOUNDATION_SERVICE_NAMESPACE}', self.foundation_service_namespace)
            create_operator_sub_cmd = "oc apply -f " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config portworx --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken.decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)    
        elif(assembly == "Zen"):
            install_cmd = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config portworx --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken.decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)    
        elif(assembly == "WSL"):
            
        elif(assembly == "WML"):

        else:
            TR.error(methodName,"Invalid storage type : %s"%self.storage_type)

        set_global_pull_secret_command  = "./setup-global-pull-secret " + self.image_registry_url + " " + self.image_registry_user  + " " + self.image_registry_password

        TR.info(methodName,"Setting global pull secret with command %s"%set_global_pull_secret_command)
        try:
            crio_retcode = check_output(['bash','-c', set_global_pull_secret_command]) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        TR.info(methodName,"Setting global pull secret with command %s returned %s"%(create_crio_mc,crio_retcode))
   
        time.sleep(300)

    #endDef

    def createCustomResource(self, assembly,storge_type, icpdInstallLogFile):

        methodName = "createCustomResource"
        TR.info(methodName,"Start creating Operator Subscription")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")


         if(assembly == "Zen"):
            install_cmd = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config portworx --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken.decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)    
        elif(assembly == "WSL"):
            
        elif(assembly == "WML"):

        else:
            TR.error(methodName,"Invalid storage type : %s"%self.storage_type)

        set_global_pull_secret_command  = "./setup-global-pull-secret " + self.image_registry_url + " " + self.image_registry_user  + " " + self.image_registry_password

        TR.info(methodName,"Setting global pull secret with command %s"%set_global_pull_secret_command)
        try:
            crio_retcode = check_output(['bash','-c', set_global_pull_secret_command]) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        TR.info(methodName,"Setting global pull secret with command %s returned %s"%(create_crio_mc,crio_retcode))
    #endDef

    def installControlPlaneAirgap(self, assembly, load_from_path, icpdInstallLogFile):
        """
        method to install Cloud Pak for Data control plane

        """
        methodName = "installControlPlaneAirgap"
  
        #Create the IBM Cloud Pak foundational services catalog source

        cs_foundcaiton_creation_cmd = self.installer_path + " case launch --case " + self.offline_dir_path + "/" + self.FoundationalService_Case_Name + " --inventory ibmCommonServiceOperatorSetup --namespace openshift-marketplace --action install-catalog --args \"--registry " + self.image_registry_url + " --inputDir " + self.offline_dir_path + " --recursive\""

        TR.info(methodName,"Execute catalog source creation command for foundational services %s"%cs_foundcaiton_creation_cmd)
        try:
            retcode = call(cs_foundcaiton_creation_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Execute catalog source creation command for foundational services %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
        
        #apply
        apply_cmd = self.installer_path +" adm --assembly " + assembly + " --latest-dependency -n "+self.namespace+ " --load-from " + load_from_path + " --accept-all-licenses --apply | tee "+self.log_dir +"/"+assembly+"_apply.log"
        TR.info(methodName,"Execute apply command for assembly %s"%apply_cmd)
        try:
            retcode = call(apply_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed apply command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
        
        #install
        TR.info("debug","self.storage_type= %s" %self.storage_type)
        TR.info("debug","self.storage_class= %s" %self.storage_class)
        
        if(self.storage_type == "portworx"):
            install_cmd = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config portworx --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken.decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            install_cmd_for_print = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config portworx --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + base64.b64encode(self.ocToken).decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)    
        elif(self.storage_type == "ocs"):
            install_cmd = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config ocs --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken.decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            install_cmd_for_print = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config ocs --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + base64.b64encode(self.ocToken).decode("ascii")+ " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)
        elif(self.storage_type == "nfs"):
            install_cmd = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken.decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            install_cmd_for_print = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + base64.b64encode(self.ocToken).decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)
        else:
            TR.error(methodName,"Invalid storage type : %s"%self.storage_type)
        try:
            retcode = call(install_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed install command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"Exception while installing service %s with message %s" %(assembly,e))
            self.rc = 1


    def installAssembliesAirgap(self, assembly, load_from_path, icpdInstallLogFile):
        """
        method to install assemlies
        for each assembly this method will execute adm command to apply all prerequistes
        Images will be pushed to local registry
        Installation will be done for the assembly using local registry
        """
        methodName = "installAssembliesAirgap"

        registry = self.regsitry.decode("ascii")+"/"+self.namespace
  
        #push
        push_cmd = self.installer_path + " preload-images --assembly " + assembly + " --action push --load-from " + load_from_path + " --transfer-image-to " + registry + " --target-registry-username "+ self.ocp_admin_user + " --target-registry-password "+ self.ocToken.decode("ascii") + " --insecure-skip-tls-verify --accept-all-licenses | tee "+self.log_dir +"/"+assembly+"_push.log"
        push_cmd_for_print = self.installer_path + " preload-images --assembly " + assembly + " --action push --load-from " + load_from_path + " --transfer-image-to " + registry + " --target-registry-username "+ self.ocp_admin_user + " --target-registry-password " + base64.b64encode(self.ocToken).decode("ascii") + " --insecure-skip-tls-verify --accept-all-licenses | tee "+self.log_dir +"/"+assembly+"_push.log"
        TR.info(methodName,"Execute push command for assembly %s"%push_cmd_for_print)
        try:
            retcode = call(push_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed push command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
        
        #apply
        apply_cmd = self.installer_path +" adm --assembly " + assembly + " --latest-dependency -n "+self.namespace+ " --load-from " + load_from_path + " --accept-all-licenses --apply | tee "+self.log_dir +"/"+assembly+"_apply.log"
        TR.info(methodName,"Execute apply command for assembly %s"%apply_cmd)
        try:
            retcode = call(apply_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed apply command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
        
        #install
        TR.info("debug","self.storage_type= %s" %self.storage_type)
        TR.info("debug","self.storage_class= %s" %self.storage_class)
        
        if(self.storage_type == "portworx"):
            install_cmd = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config portworx --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken.decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            install_cmd_for_print = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config portworx --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + base64.b64encode(self.ocToken).decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)    
        elif(self.storage_type == "ocs"):
            install_cmd = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config ocs --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken.decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            install_cmd_for_print = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config ocs --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + base64.b64encode(self.ocToken).decode("ascii")+ " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)
        elif(self.storage_type == "nfs"):
            install_cmd = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken.decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            install_cmd_for_print = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --load-from " + load_from_path +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + base64.b64encode(self.ocToken).decode("ascii") + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
            TR.info(methodName,"Execute install command for assembly %s"%install_cmd_for_print)
        else:
            TR.error(methodName,"Invalid storage type : %s"%self.storage_type)
        try:
            retcode = call(install_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed install command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"Exception while installing service %s with message %s" %(assembly,e))
            self.rc = 1


 
    def validateInstall(self, icpdInstallLogFile):
        """
            This method is used to validate the installation at the end. At times some services fails and it is not reported. 
            We use this method to check if cpd operator is up and running. We will then get the helm list of deployed services and validate for each of the services selected by user. IF the count adds up to the defined count then installation is successful. Else  will be flagged it as failure back to cloud Formation.
        """

        methodName = "validateInstall"
        count = 3
        TR.info(methodName,"Validate Installation status")
        if(self.installDV == "True"):
            count = count+1
        if(self.installOSWML == "True"):
            count = count+1    
        if(self.installSpark == "True"):
            count = count+1    
        if(self.installWKC == "True"):
            count = count+6
        if(self.installCDE == "True"):
            count = count+1
        if(self.installWML == "True"):
            count = count+2
        if(self.installWSL == "True"):
            count = count+4            

        # CCS Count
        if(self.installCDE == "True" or self.installWKC == "True" or self.installWSL == "True" or self.installWML == "True"):
            count = count+8
        # DR count    
        if(self.installWSL == "True" or self.installWKC == "True"):
            count = count+1                

        operator_pod = "oc get pods | grep cpd-install-operator | awk '{print $1}'"
        operator_status = "oc get pods | grep cpd-install-operator | awk '{print $3}'"
        validate_cmd = "oc exec -it $(oc get pods | grep cpd-install-operator | awk '{print $1}') -- helm list --tls"
        operator = check_output(['bash','-c',operator_pod])
        TR.info(methodName,"Operator pod %s"%operator)
        if(operator == ""):
            self.rc = 1
            return
        op_status = check_output(['bash','-c',operator_status])
        TR.info(methodName,"Operator pod status is %s"%op_status)
        if(op_status.rstrip()!="Running"):
            self.rc = 1
            return   
        install_status = check_output(['bash','-c',validate_cmd])
        TR.info(methodName,"Installation status is %s"%install_status)
        #TR.info(methodName,"Actual Count is %s Deployed count is %s"%(count,install_status.count("DEPLOYED")))
        #if(install_status.count("DEPLOYED")< count):
        #    self.rc = 1
        #    TR.info(methodName,"Installation Deployed count  is %s"%install_status.count("DEPLOYED"))
        #    return   

    #endDef          
    
    def _loadConf(self):
        methodName = "loadConf"
        TR.info(methodName,"Start load installation configuration")
        config = configparser.ConfigParser()
        config.read('../cpd_install.conf')

        self.ocp_admin_user = config['ocp_cred']['ocp_admin_user'].strip()
        self.ocp_admin_password = config['ocp_cred']['ocp_admin_password'].strip()
        self.image_registry_url = config['image_registry']['image_registry_url'].strip()
        self.image_registry_user = config['image_registry']['image_registry_user'].strip()
        self.image_registry_password = config['image_registry']['image_registry_password'].strip()
        self.change_node_settings = config['settings']['change_node_settings'].strip()
        self.config_image_pull = config['settings']['config_image_pull'].strip()
        self.log_dir = config['cpd_assembly']['log_dir'].strip()
        self.overall_log_file = config['cpd_assembly']['overall_log_file'].strip()
        self.offline_dir_path = config['cpd_assembly']['offline_dir_path'].strip()
        self.installer_path = config['cpd_assembly']['installer_path'].strip()
        self.installWSL = config['cpd_assembly']['installWSL'].strip()
        self.installWML = config['cpd_assembly']['installWML'].strip()
        self.installWKC = config['cpd_assembly']['installWKC'].strip()
        self.installSpark = config['cpd_assembly']['installSpark'].strip()
        self.installCDE = config['cpd_assembly']['installCDE'].strip()
        self.installDV = config['cpd_assembly']['installDV'].strip()
        self.installOSWML = config['cpd_assembly']['installOSWML'].strip()
        self.installRStudio = config['cpd_assembly']['installRStudio'].strip()
        self.installSPSS = config['cpd_assembly']['installSPSS'].strip()       
        self.installRuntimeGPUPy37 = config['cpd_assembly']['installRuntimeGPUPy37'].strip()
        self.installRuntimeR36 = config['cpd_assembly']['installRuntimeR36'].strip()
        self.installHEE = config['cpd_assembly']['installHEE'].strip()
        self.installDODS = config['cpd_assembly']['installDODS'].strip()
        self.storage_type = config['cpd_assembly']['storage_type'].strip()    
        self.storage_class = config['cpd_assembly']['storage_class'].strip()        
        self.foundation_service_namespace = config['cpd_assembly']['foundation_service_namespace'].strip()
        self.cpd_operator_namespace = config['cpd_assembly']['cpd_operator_namespace'].strip()
        self.cpd_instance_namespace = config['cpd_assembly']['cpd_instance_namespace'].strip()
        self.cpd_license = config['cpd_assembly']['cpd_license'].strip()
        TR.info(methodName,"Load installation configuration completed")
        TR.info(methodName,"Installation configuration:" + self.ocp_admin_user + "-" + self.ocp_admin_password  + "-" + self.installer_path)
    #endDef

    def main(self,argv):
        methodName = "main"
        self.rc = 0
        try:
            beginTime = Utilities.currentTimeMillis()
           
            self._loadConf()   
      
            if (self.overall_log_file):
                TR.appendTraceLog(self.overall_log_file)   

            logFilePath = os.path.join(self.logsHome,"icpd_install.log")

            with open(logFilePath,"a+") as icpdInstallLogFile:  
                ocpstart = Utilities.currentTimeMillis()
                TR.info("debug","change_node_settings= %s" %self.change_node_settings)
                if(self.change_node_settings == "True"):
                    self.changeNodeSettings(icpdInstallLogFile)
                    TR.info("debug","Finishd the node settings")
                    ocpend = Utilities.currentTimeMillis()
                    self.printTime(ocpstart, ocpend, "Chaning node settings")
                
                TR.info("debug","config_image_pull= %s" %self.config_image_pull)
                
                ocpstart = Utilities.currentTimeMillis()
                if(self.config_image_pull == "True"):
                    self.configImagePull(icpdInstallLogFile)
                    TR.info("debug","Finishd the image pull configuration")
                    ocpend = Utilities.currentTimeMillis()
                    self.printTime(ocpstart, ocpend, "Configuring image pull")

                if(self.installOSWML == "True"):
                    self.installWML="True"
                
                TR.info("debug","image_registry_url= %s" %self.image_registry_url)
                TR.info("debug","image_registry_user= %s" %self.image_registry_user)
                TR.info("debug","image_registry_password= %s" %self.image_registry_password)
                TR.info("debug","foundation_service_namespace= %s" %self.foundation_service_namespace)
                TR.info("debug","cpd_operator_namespace= %s" %self.cpd_operator_namespace)
                TR.info("debug","cpd_instance_namespace= %s" %self.cpd_instance_namespace)

                TR.info("debug","installWSL= %s" %self.installWSL)
                TR.info("debug","installWML= %s" %self.installWML)
                TR.info("debug","installWKC= %s" %self.installWKC)
                TR.info("debug","installDV= %s" %self.installDV)
                TR.info("debug","installDMC= %s" %self.installDMC)
                TR.info("debug","installOSWML= %s" %self.installOSWML)
                TR.info("debug","installCDE= %s" %self.installCDE)
                TR.info("debug","installSpark= %s" %self.installSpark)
                TR.info("debug","installRStudio= %s" %self.installRStudio)
                TR.info("debug","installSPSS= %s" %self.installSPSS)
                TR.info("debug","installRuntimeGPUPy37= %s" %self.installRuntimeGPUPy37)
                TR.info("debug","installRuntimeR36= %s" %self.installRuntimeR36)
                TR.info("debug","installHEE= %s" %self.installHEE)
                TR.info("debug","installDODS= %s" %self.installDODS)

               
                getTokenCmd = "oc whoami -t"

                try:
                    self.ocToken = check_output(['bash','-c', getTokenCmd])
                    self.ocToken = self.ocToken.strip('\n'.encode('ascii'))
                    TR.info(methodName,"Completed %s command with return value (encoded) %s" %(getTokenCmd,base64.b64encode(self.ocToken))
                except CalledProcessError as e:
                    TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

                self.installCPD(icpdInstallLogFile)
                
                self.installStatus = "CPD Installation completed"
                TR.info("debug","Installation status - %s" %self.installStatus)


                self.validateInstall(icpdInstallLogFile)


                self.installStatus = "Finished validating installation"
                TR.info("debug","Installation status - %s" %self.installStatus)

            #endWith    
            
        except Exception as e:
            TR.error(methodName,"Exception with message %s" %e)
            self.rc = 1

        endTime = Utilities.currentTimeMillis()
        elapsedTime = (endTime - beginTime)/1000
        etm, ets = divmod(elapsedTime,60)
        eth, etm = divmod(etm,60) 

        if (self.rc == 0):
            success = 'true'
            status = 'SUCCESS'
            TR.info(methodName,"SUCCESS END CPD Quickstart.  Elapsed time (hh:mm:ss): %d:%02d:%02d" % (eth,etm,ets))
        else:
            success = 'false'
            status = 'FAILURE: Check logs on the Boot node in /ibm/logs/icpd_install.log and /ibm/logs/post_install.log'
            TR.info(methodName,"FAILED END CPD Quickstart.  Elapsed time (hh:mm:ss): %d:%02d:%02d" % (eth,etm,ets))
        #endIf                                            
    #end Def    
#endClass
if __name__ == '__main__':
  mainInstance = CPDInstall()
  mainInstance.main(sys.argv)
#endIf
