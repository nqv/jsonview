#!/usr/bin/env python
import os, sys, subprocess, tempfile, shutil
import getopt
import json, ConfigParser
import xml.etree.ElementTree as ET
import zipfile

NAME = "jsonview"
VERSION = json.load(open("package.json"))["version"]
XPI_NAME = "{}-{}.xpi".format(NAME, VERSION)

profileDir = None

# Search for profile dir
def getProfileDir(profileName):
  if os.name == "nt":
    homeDir = os.path.join(os.getenv("APPDATA"), "Mozilla", "Firefox")
  else:
    homeDir = os.path.join(os.path.expanduser("~"), ".mozilla", "firefox")

  profilesPath = os.path.join(homeDir, "profiles.ini")
  config = ConfigParser.ConfigParser()
  config.read(profilesPath)

  for section in config.sections():
    if section.startswith("Profile") \
        and config.get(section, "Name") == profileName:
      return os.path.join(homeDir, config.get(section, "Path"))
  return None

# Copy all localized description tags
def copyLocalizedDescription(source, target):
  RDF_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  EM_NAMESPACE = "http://www.mozilla.org/2004/em-rdf#"

  targetTree = ET.parse(target)
  targetDesc = targetTree.getroot().find("./{{{}}}Description" \
      .format(RDF_NAMESPACE))

  sourceTree = ET.parse(source)
  sourceTagName = "./{{{}}}Description/{{{}}}localized" \
      .format(RDF_NAMESPACE, EM_NAMESPACE)

  for a in sourceTree.getroot().findall(sourceTagName):
    targetDesc.append(a)

  ET.register_namespace("", RDF_NAMESPACE)
  ET.register_namespace("em", EM_NAMESPACE)
  targetTree.write(target, "utf-8", True)

# Unpack a xpi to a folder
def unpackXpi(source, target):
  xpi = zipfile.ZipFile(source, "r")
  xpi.extractall(target)
  xpi.close()

# Recreate a xpi file from a folder
def packXpi(source, target):
  xpi = zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED)

  for dirPath, dirNames, fileNames in os.walk(source):
    for name in fileNames:
      filePath = os.path.join(dirPath, name)
      relPath = os.path.relpath(filePath, source)
      xpi.write(filePath, relPath)

  xpi.close()

# Mozilla bug 661083
# Addon metadata can not be localized. It requires unpacking the xpi,
# updating the install.rdf and compressing everything again.
def fixLocalizedDescription():
  targetDir = tempfile.mkdtemp()
  targetFile = "install.rdf"

  unpackXpi(XPI_NAME, targetDir)
  copyLocalizedDescription(os.path.join("src", targetFile), \
      os.path.join(targetDir, targetFile))
  packXpi(targetDir, "fixed-" + XPI_NAME)

  # Cleanup
  shutil.rmtree(targetDir)

# Generate XPI file
def createXpi():
  args = ["cfx", "xpi", "--output-file=" + XPI_NAME]
  return subprocess.call(args)

# Run in browser
def run(profileDir):
  args = ["cfx", "run"]
  if profileDir is not None:
    args.append("-p")
    args.append(profileDir)

  return subprocess.call(args)

# Usage
def printUsage():
  print("Usage: {} [OPTIONS...] COMMAND".format(sys.argv[0]))
  print("""
COMMANDS:
  xpi     Create xpi file
  run     Run the addon
  fix     Fix localized description in generated xpi

OPTIONS:
  -p PROFILE, --profile=PROFILE
          Used with command 'run'. Open the addon with the specific browser
          profile. PROFILE can be either an absolute path or a profile name
          (i.e. 'dev'), which then be translated to profile path in
          ~/.mozilla/firefox
""")

if __name__ == "__main__":
  try:
    opts, args = getopt.getopt(sys.argv[1:], "p:", ["profile="])
  except getopt.GetoptError as err:
    print(str(err))
    printUsage()
    sys.exit(1)

  for o, a in opts:
    if o in ("-p", "--profile"):
      profileDir = a
    else:
      print("Unhandled option: {}".format(o))
      printUsage()
      sys.exit(1)

  # If profile is just a name, search for full path
  if profileDir is not None \
      and "/" not in profileDir \
      and "\\" not in profileDir:
    profileDir = getProfileDir(profileDir)
    if profileDir is None:
      print("Profile {} does not exist.".format(profileName))
      sys.exit(1)

  # Default command is xpi
  if not args:
    cmd = "xpi"
  else:
    cmd = args[0]

  if cmd == "run":
    sys.exit(run(profileDir))
  elif cmd == "xpi":
    sys.exit(createXpi())
  elif cmd == "fix":
    sys.exit(fixLocalizedDescription())
  else:
    print("Command: {} is not supported".format(cmd))
    printUsage()
    sys.exit(1)
