import os
import requests
import websocket
import copy
from slackclient import SlackClient
import time
import re
from lxml import html
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET
import datetime
import json
import sys



slack_token='<slack token>'
#slack_token = os.environ["SLACK_API_TOKEN"]
proxies = dict(https="https://server:port",http="http://server:port")
#sc = SlackClient(slack_token, proxies=proxies)
#sc = SlackClient(slack_token)
# instantiate Slack client
slack_client = SlackClient(slack_token, proxies=proxies)
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM

MENTION_REGEX = "<@(|[WU].+?)>(.*)"

bamboo_base_url = '<bamboo base url>'

bamboo_api_url = bamboo_base_url + '/rest/api/latest'
bamboo_test_url = bamboo_base_url + '/browse/'


session = requests.Session()
session.verify = False
session.auth = ('<username>', '<password>')
config = json.loads(open('config.json').read())
notFoundMessage = "I do not have details about this!!"
GREET_COMMAND = "Try Somethng like - 'I need status for <unique name of the job as defined in the config,json> '"
keyErrorMessage = "Seems the key is incorrect for this name!!"

def GetTestStatus(name):
    name = GetFormattedName (name)
    for item in config:
      #if item['EnvName'].lower() == envName.lower() and item['testType'].lower() == testType.lower():
      formattedName = GetFormattedName (item['name'])
      print ('formattedName'+formattedName)
      print ('actual name'+name)
      if formattedName == name:
            job_key = item['job_key']
            try:
                response = session.get(bamboo_api_url + '/result/' + job_key + '/latest?expand=results.result')
                response.raise_for_status()
                root = ET.fromstring(response.text)
                build_state = root.find('buildState').text
                passed_tests = root.find('successfulTestCount').text
                failed_tests = root.find('failedTestCount').text
                quarantined_tests = root.find('quarantinedTestCount').text
                skipped_tests = root.find('skippedTestCount').text
                lastRun = root.find('prettyBuildStartedTime').text
                result = "*{}*.".format(build_state)+"\n"+"*{}*.".format("Test Summary")+"\n"+"{}".format("Last Run On: ")+lastRun+"\n"+"{}".format("Passed Tests: ")+passed_tests+"\n"+"{}".format("Failed Tests: ")+failed_tests+"\n"+"{}".format("Skipped Tests: ")+skipped_tests
                return result
            except:
                return keyErrorMessage
      #else:
            #return notFoundMessage
    return notFoundMessage

def GetRunStatus(job_key,nextBuildNum):
	runStatus = session.get(bamboo_api_url + '/result/status/' + job_key+'-'+nextBuildNum)
	root = ET.fromstring(runStatus.text)
	runStatusCode = (str(runStatus).split(" ")[-1].split("[")[-1].split("]")[-2])
	return runStatusCode

def GetLatestBuildNum(job_key):
    page=session.get(bamboo_test_url + job_key)
    print (bamboo_test_url + job_key)
    tree = html.fromstring(page.content)
    buildId = tree.xpath('//*[@id="buildResultsTable"]/tbody/tr/td/a/@href')
    buildNum = int(buildId[0].split("/")[-1].split("-")[-1])
    #xpathEl = '//*[@id="breadcrumb:'+job_key+'"]'
   # //*[@id="breadcrumb:DEVOPS-PT"]
    #print (xpathEl)
    #buildName = tree.xpath(xpathEl)[0].text
    #print ('buildName')
    #print (buildName)
    return buildNum

def GetBuildDetails(job_key):
    page=session.get(bamboo_test_url + job_key)
    #print (bamboo_test_url + job_key)
    tree = html.fromstring(page.content)
    xpathEl = '//*[@id="breadcrumb:'+job_key+'"]'
    #print (xpathEl)
    buildName = tree.xpath(xpathEl)[0].text
    return buildName


def GetFormattedName(name):
    name = name.replace(" ","").lower()
    return name

def Trigger(job_key,nextBuildNum):
    test = {'Content-type':'application/json', 'Authorization':'Basic bmVlcmFqczpBZG1pbkA1NDM='}
    runStatusCode = GetRunStatus(job_key,nextBuildNum)
    if runStatusCode != '200':
        response = session.post(bamboo_api_url + '/queue/' + job_key + '?stage=default&executeAllStages=True',headers=test)
        triggerStatusCode = (str(response).split(" ")[-1].split("[")[-1].split("]")[-2])
        print ('trigger status code '+triggerStatusCode)
    if triggerStatusCode == '200':
        print ('triggered the build')
        responseMsg = "Build Triggered with key: "+job_key+"-"+nextBuildNum
        runStatusCode = '200'
    else:
        print ('could not trigger the build')
        responseMsg = "Could not trigger the build with key: "+job_key+"-"+nextBuildNum
    return responseMsg

def TriggerBuild(name):
    test = {'Content-type':'application/json', 'Authorization':'Basic bmVlcmFqczpBZG1pbkA1NDM='}
    for item in config:
        formattedName = GetFormattedName (item['name'])
        print (formattedName)
        name = GetFormattedName (name)
        print (name)
      #if item['EnvName'].lower() == envName.lower() and item['testType'].lower() == testType.lower():
        if formattedName == name:
            job_key = item['job_key']
            buildNum = GetLatestBuildNum(job_key)  
            nextBuildNum = str(buildNum+1)
            print (nextBuildNum)
            print (bamboo_api_url + '/result/status/' + job_key+'-'+nextBuildNum)
            runStatusCode = GetRunStatus(job_key,nextBuildNum)
            print (runStatusCode)
            if runStatusCode != '200':
                responseMsg = Trigger(job_key,nextBuildNum)
            elif runStatusCode == '200':
                print ('inside')
                runStatus = session.get(bamboo_api_url + '/result/status/' + job_key+'-'+nextBuildNum)
                print (runStatus)
                root = ET.fromstring(runStatus.text)
                print (root.find('progress').find('prettyTimeRemaining').text)
              #expBuildCompletionTime = root[1].find('prettyTimeRemaining').text
                expBuildCompletionTime = root.find('progress').find('prettyTimeRemaining').text
                print (expBuildCompletionTime)
                responseMsg = "Build is already in progress for this plan,Estimated completion time is: "+expBuildCompletionTime
            return responseMsg
        #   while runStatusCode == '200':
        #       print ('still building..')
        #       time.sleep(1)
        #       runStatusCode = GetRunStatus(job_key,nextBuildNum)
        #       print (runStatusCode)
        #       res
        #       if(runStatusCode!='200'):
        #           status = GetTestStatus(envName,testType)
        #           print ('build completed')
        #           responseMsg = "Build is completed!!!"+status
        #           break
        #       else:
        #           continue
        #   return responseMsg
    return notFoundMessage
def AddBuild(key,name):
    data = {'job_key':key,'name':name}
    config = json.loads(open('config.json').read())
    config.append(data)
    with open("config.json", 'w') as f:
        json.dump(config,f)
    os.execl(sys.executable, sys.executable, * sys.argv)
    print ('bot started again')


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            user = (event["user"])
            print ("<@{}>!".format(user))
            if user_id == starterbot_id:
              if message=="":
                message = "hello"
                return message , event["channel"] ,user 
              return message , event["channel"] ,user
    return None, None,None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)

    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(command, channel ,user):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    unformattedCommand = command
    print ('unformattedCommand is '+unformattedCommand)
    namelst = list()
    lst = list()
    entireList = list()
    for item in config:
      #envName = item['EnvName']+" "+item['testType']
      item_name = item['name']
      item_key = item['job_key']
      #buildName = GetBuildDetails(item_key)
      #displayName = item_name+" "+buildName+" "+item_key
      combo = item_name+"."+item_key
      #testType = item['testType']
      lst.append(item_name)
      namelst.append(combo)
      #entireList.append(displayName)
    print (lst)
    #print(entireList)

    for item in namelst:
      temp = GetFormattedName(item.split(".")[0])
      command = GetFormattedName(command)
      print ('formatted comand '+command)
      print ('name is '+temp)
      #print ('item is '+item)
      if temp in command:
          name = temp
          unformattedName = item.split(".")[0]
          jobKey = item.split(".")[1]
          print ('got it '+name)
          break
      else:
          name = 'none'

    default_response = "Hello <@{}>!!".format(user)+" :wave: "+".. *{}*.".format(GREET_COMMAND)+"\n"+"I can provide info about following "+"\n"+"\n".join(str(x) for x in lst)

    # Finds and executes the given command, filling in response
    response = None


        
    # if (name!='none' or 'hi' not in command or 'hello' not in command):
    #     print ('got :
    # name as ' +name)
    if 'hi' in command:
        response = default_response
    elif 'add' in unformattedCommand or 'Add' in unformattedCommand:
        commandParts = unformattedCommand.split(" ")
        print (commandParts)
        if len(commandParts)==3:
            key = commandParts[-2]
            name = commandParts[-1]
            response = "Adding key..Bot would restart"
            #time.sleep(1)
            AddBuild(key.upper(),name)          
        else:
            response = "Cannot find key!!Try Something like: add <key> <name>"
    elif 'trigger' not in command:
        status = GetTestStatus(name)
        print ("status message is "+status)
        if status == notFoundMessage:
            response = "Hello <@{}>!!".format(user)+ ":disappointed: " +notFoundMessage+"\n Try one from the following"+"\n"+"\n".join(str(x) for x in lst)
        elif status == keyErrorMessage:
            print('inside the rror')
            response = keyErrorMessage
        else:
            job_key = jobKey
            print('job key is '+job_key)
                #job_key = item['job_key']
            buildNum = GetLatestBuildNum(job_key)  
            nextBuildNum = str(buildNum+1)
            print (nextBuildNum)
            print (bamboo_api_url + '/result/status/' + job_key+'-'+nextBuildNum)
            runStatusCode = GetRunStatus(job_key,nextBuildNum)
            print (runStatusCode)
            if runStatusCode == '200':
                responseMsg = TriggerBuild(name)
                print ('inside')
                runStatus = session.get(bamboo_api_url + '/result/status/' + job_key+'-'+nextBuildNum)
                print (runStatus)
                root = ET.fromstring(runStatus.text)
                print (root.find('progress').find('prettyTimeRemaining').text)
                expBuildCompletionTime = root.find('progress').find('prettyTimeRemaining').text
                print (expBuildCompletionTime)
                responseMsg = "Build is already in progress for this plan,Estimated completion time is: "+expBuildCompletionTime
                response = "Hi <@{}>!!".format(user)+" The last build status for "+unformattedName+" is "+ status+"\n"+".. *{}*.".format("A newer build is in progress with "+expBuildCompletionTime)+"\n"+".. *{}*.".format("Check Later for status of the latest build..")
                print (response)
            elif runStatusCode != '200':
                response = "Hi <@{}>!!".format(user)+" The Last build status for "+unformattedName+" is "+ status+"\n"+"To trigger a new build ,try Something like - " +"*{}*.".format("Trigger build "+unformattedName)
    elif 'trigger' or 'Trigger' in command:
        print ("Happy to trigger")
        responseMsg = TriggerBuild(name)
        if responseMsg == notFoundMessage:
            response = ":disappointed: "+notFoundMessage+"\n Try one from the following"+"\n"+"\n".join(str(x) for x in lst)
        else:
            response = responseMsg

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )

if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel ,user = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel,user)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")