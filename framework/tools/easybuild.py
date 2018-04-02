############################################################################
#
#  Copyright 2017
#
#   https://github.com/HPC-buildtest/buildtest-framework
#
#  This file is part of buildtest.
#
#    buildtest is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    buildtest is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with buildtest.  If not, see <http://www.gnu.org/licenses/>.
#############################################################################

"""
easybuild specific modules related to toolchain and easyconfigs

:author: Shahzeb Siddiqui
"""
import os
import re
import sys
import logging
import subprocess

from framework.env import logID, config_opts
from framework.tools.file import stripHiddenFile, isHiddenFile, string_in_file
from framework.tools.utility import get_appname, get_appversion, get_toolchain_name, get_toolchain_version


# return root of module directory for all EasyBuild Trees in BUILDTEST_EBROOT
def get_module_ebroot():
    modroot = []
    for tree in config_opts['BUILDTEST_EBROOT']:
        if os.path.exists(os.path.join(tree,"modules")):
            modroot.append(os.path.join(tree,"modules"))
        else:
            print "Invalid EasyBuild Tree, please check your BUILDTEST_EBROOT in config.yaml"
            sys.exit(1)
    return modroot

# return root of software directory for all EasyBuild Trees in BUILDTEST_EBROOT
def get_software_ebroot():
    swroot = []
    for tree in config_opts['BUILDTEST_EBROOT']:
        if os.path.exists(os.path.join(tree,"software")):
            swroot.append(os.path.join(tree,"software"))
        else:
            print "Invalid EasyBuild Tree, please check your BUILDTEST_EBROOT in config.yaml"
            sys.exit(1)

    return swroot

def list_toolchain():
        """
        return the set of toolchains found in the easyconfig directory
        """
        toolchain = [
        "ClangGCC",
        "CrayCCE",
        "CrayGNU",
        "CrayIntel",
        "CrayPGI",
        "GCC",
        "GCCcore",
        "GNU",
        "PGI",
        "cgmpich",
        "cgmpolf",
        "cgmvapich2",
        "cgmvolf",
        "cgompi",
        "cgoolf",
        "dummy",
        "foss",
        "gcccuda",
        "gimkl",
        "gimpi",
        "gmacml",
        "gmpich",
        "gmpich2",
        "gmpolf",
        "gmvapich2",
        "gmvolf",
        "goalf",
        "gompi",
        "gompic",
        "goolf",
        "goolfc",
        "gpsmpi",
        "gpsolf",
        "gqacml",
        "iccifort",
        "iccifortcuda",
        "ictce",
        "iimkl",
        "iimpi",
        "iimpic",
        "iiqmpi",
        "impich",
        "impmkl",
        "intel",
        "intel-para",
        "intelcuda",
        "iomkl",
        "iompi",
        "ipsmpi",
        "iqacml",
        "ismkl",
        "pomkl",
        "pompi",
        "xlcxlf",
        "xlmpich",
        "xlmpich2",
        "xlmvapich2",
        "xlompi",
        ]

        logger = logging.getLogger(logID)
        logger.info("List of EB Toolchains")
        logger.info("--------------------------------------")
        logger.info("EB Toolchains = %s", toolchain)

        return toolchain

def find_easyconfigs():
    """ returns easyconfigs files from a module tree. """
    from framework.tools.modules import get_module_list
    BUILDTEST_SOFTWARE_EBROOT = config_opts.get('DEFAULT','BUILDTEST_SOFTWARE_EBROOT')
    BUILDTEST_EBROOT = config_opts['BUILDTEST_EBROOT']

    modtree = get_module_ebroot()

    ec_list = []
    no_ec_list = []
    modulelist = get_module_list()
    

    # look for variable root in modulefile
    search_str = "local root ="
    for module in  modulelist:
        # if variable root found in module file then read file and find value assigned to root to get root of software
        if string_in_file(search_str,module):
            content = open(module).readlines()
            for line in content:
                if line.startswith(search_str):
                    root_path = line.split()[-1]
                    root_path = root_path.replace('"','')
                    easybuild_path = os.path.join(root_path,"easybuild")
                    # if directory exist then run the find command
                    if os.path.exists(easybuild_path):
                        cmd = "find " + easybuild_path + " -type f -name *.eb "
                        ret = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE)
                        easyconfig = ret.communicate()[0]
                        easyconfig = easyconfig.strip("\n")
                        #print cmd,easyconfig
                        # only add easyconfigs to list using find command. This also avoids adding empty entries when no file was found
                        if os.path.exists(easyconfig):
                            ec_list.append(easyconfig)
                        else:
                            no_ec_list.append("Could not find easyconfig in " + easybuild_path)
                    else:
                        print "Unable to find directory: ", easybuild_path
                    break
                else:
                    continue

    print "List of easyconfigs found in MODULETREES:", config_opts['BUILDTEST_EBROOT']
    print
    print "ID   |    easyconfig path"
    print "-----|--------------------------------------------------------------------"
    count = 1
    for ec in ec_list:
        print (str(count) + "\t |").expandtabs(4),ec
        count = count + 1

    if len(no_ec_list) > 0:
        print
        print "Unable to find easyconfigs for the following, please investigate this issue! \n"

        for no_ec in  no_ec_list:
            print no_ec
    else:
        print "All easyconfigs found!"

    print "Total easyconfigs found:", len(ec_list)
    print "Total module files searched:", len(modulelist)


def check_software_version_in_easyconfig(easyconfig_repo):
        """
        return True if name,version+versionsuffix,toolchain from command line is found
        from easyconfig, False otherwise
        """
        success_msg = "Checking easyconfig conditional checks ... SUCCESS"
        fail_msg = "Checking easyconfig conditional checks ... FAILED"
        appname = get_appname()
        appversion = get_appversion()
        tcname = get_toolchain_name()
        tcversion = get_toolchain_version()

        logger = logging.getLogger(logID)
        BUILDTEST_MODULE_NAMING_SCHEME = config_opts['BUILDTEST_MODULE_NAMING_SCHEME']

        # if user is testing a software package that is a hidden module file, strip the leading "." for checking
        if isHiddenFile(appversion):
                appversion = stripHiddenFile(appversion)
                logger.debug("Stripping leading . from application version: %s ", appversion)

        # only check if toolchain version is a hidden module  when toolchain is specified by checking length
        if len(tcversion) != 0:
                # if user specified a toolchain version that is a hidden module file, strip leading "."
                if isHiddenFile(tcversion) :
                        tcversion = stripHiddenFile(tcversion)
                        logger.debug("Stripping leading . from toolchain version: %s", tcversion)

        # for Flat Naming Scheme -s will take APP/Version-Toolchain so need to take Toolchain out for comparison
        if BUILDTEST_MODULE_NAMING_SCHEME == "FNS":
                arg_tc_name = toolchain[0] + "-" + toolchain[1]
                appversion = appversion.replace(arg_tc_name,'')
                logger.debug("Detected Module Naming Scheme is Flat Naming Scheme")
                logger.debug("Removing toolchain from module version for comparision")
                # stripping last character if which is a "-" because module version in FNS
                # is <version>-<toolchain>
                if appversion[-1] == "-":
                        appversion = appversion[:-1]

        firstletter = appname[0].lower()
        ebapp_easyconfig_root = os.path.join(easyconfig_repo,firstletter,appname)
        os.chdir(ebapp_easyconfig_root)

        easyconfigfile = ""

        if len(tcname) == 0:
                easyconfigfile = appname + "-" + appversion +  ".eb"
        else:
                easyconfigfile = appname + "-" + appversion + "-" + tcname + "-" + tcversion +".eb"


        easyconfigpath = os.path.join(easyconfig_repo,firstletter,appname,easyconfigfile)
        if not os.path.exists(easyconfigpath):
                print "ERROR: No such easyconfig file: " + easyconfigpath
                print
                print "buildtest checks the easyconfig to ensure application is installed with easybuild"
                sys.exit(1)
        else:
                print "Checking for easyconfig file: " + easyconfigfile + " ... FOUND"

        # renaming variable
        ebfile = easyconfigpath

        f = open(ebfile,'r')
        content = f.readlines()

        # extracting name, version, and toolchain name/version from easyconfig file
        for line in content:
                line_name = re.match('name = ',line)
                line_version = re.match('version = ',line)
                line_toolchain = re.match('toolchain = ', line)

                if line_name:
                        name =  line.split("=")[1].replace("'","").strip()

                if line_version:
                        version = line.split("=")[1].replace("'","").strip()

                if line_toolchain:
                        # extract toolchain name/version from string: toolchain = {'name': 'intel', 'version': '2016b'}
                        startpos = line.index("{")
                        temp = line[startpos:]
                        toolchain_name = temp.split(",")[0].split(":")[1].replace("'","").strip()
                        toolchain_version = temp.split(",")[1].split(":")[1].replace("}","").replace("'","").strip()


        # if toolchain name is dummy in easyconfig, lets force it to "" so checking for dummy toolchain will be with empty quotes
        if toolchain_name == "dummy":
                toolchain_name = ""
                toolchain_version = ""

                # alter eb_name_format for dummy toolchain
                eb_name_format=name+"-"+version
        else:
                # eb name format used for comparison to calculate versionsuffx
                eb_name_format=name+"-"+version+"-"+toolchain_name+"-"+toolchain_version


        # get name of eb file
        ebname = os.path.basename(ebfile)

        logger.debug("Before Stripping File extension(.eb) - FILE: %s", ebname)

        # stripping extension ".eb"
        ebname=os.path.splitext(ebname)[0]

        logger.debug("After Stripping File extension -  FILE: %s", ebname)

        # There is no version suffix when file name is just
        # software-version-toolchain.eb
        # determine starting position index in easyconfig filename to
        # calculate versionsuffix. If its a dummy toolchain start with
        # version, otherwise from toolchain version
        if toolchain_name == "":
                startpos=ebname.find(version)+len(version)
        else:
                # extract version suffix
                startpos=ebname.find(toolchain_version)+len(toolchain_version)

        endpos=len(ebname)

        versionsuffix=ebname[startpos:endpos]

        # variable used for comparison
        version_versionsuffix=version + versionsuffix

        logger.debug("Extracting version suffix from eb name: %s",ebname)
        logger.debug("Version Suffix: %s", versionsuffix)
        logger.debug("Version + Version Suffix: %s", version_versionsuffix)

        logger.debug("\n")

        logger.debug("All CONDITIONS must pass")
        logger.debug("NAME String Comparision - STR1: %s \t STR2: %s", name, appname)
        logger.debug("VERSION String Comparision - STR1: %s \t STR2: %s", version_versionsuffix, appversion)
        logger.debug("TOOLCHAIN NAME String Comparision - STR1: %s \t STR2: %s", toolchain_name, tcname)
        logger.debug("TOOLCHAIN VERSION String Comparision - STR1: %s \t STR2: %s", toolchain_version, tcversion)
        if name == appname and version_versionsuffix == appversion and toolchain_name == tcname and toolchain_version == tcversion:
                logger.debug("All Checks have PASSED!")

                print success_msg
                return True
        else:
                print "ERROR: failed to pass all checks in easyconfig, make sure Application & Toolchain name/version match in easyconfig"
                logger.debug("ERROR: FAILED to pass all checks!")
                sys.exit(1)
