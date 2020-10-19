//*************************************************************
// JS-Handler-Script for Alexa4P3
//
// (C) Andre Kohler             andre.kohler01@googlemail.com
// 
// Change-Log
//
// 2020-03-28   -   added Test-Functions to Web-IF
// 2019-12-18   -   Change-Log eingeführt
//*************************************************************




//*************************************************************
// check Auto-Updates for protocols
//*************************************************************
setInterval(Checkupdate4Protocolls, 5000);


//*************************************************************
// delete Protocols
//*************************************************************

function DeleteProto(btn_Name)
{

 if (btn_Name == "btn_clear_proto_states")
    { proto_Name = "webif.state_protocoll"} 

 $.ajax({
    url: "clear_proto.html",
    type: "GET",
    data: { proto_Name : proto_Name
          },
    contentType: "application/json; charset=utf-8",
    success: function (response) {
		     ClearProto(proto_Name);
    },
    error: function () {
        console.log("Error - while clearing Protocol :"+proto_Name)
    }
 });
};

//*************************************************************
// clear Protocol
//*************************************************************
function ClearProto(proto_Name)
{

    if (proto_Name == 'webif.state_protocoll')
    {
        statelogCodeMirror.setValue("")
    }
}


//*************************************************************
// check Auto-Updates for protocols
//*************************************************************
function Checkupdate4Protocolls()
{ 
    states_checked = document.getElementById("proto_states_check").checked
    if (states_checked == true)
    {
     UpdateProto('state_log_file')
    }
}


//*************************************************************
// actualisation of Protocol
//*************************************************************
function actProto(response,proto_Name)
{
    myProto = document.getElementById(proto_Name)
    myProto.value = ""
    myText = ""
    var objResponse = JSON.parse(response)
    for (x in objResponse)
        {
         myText += objResponse[x]+"\n"
        }
    myProto.value = myText
    if (proto_Name == 'state_log_file')
    {
        statelogCodeMirror.setValue(myText)
    }
}

//*************************************************************
// Auto-Update-Timer for protocol - States
//*************************************************************

function UpdateProto(proto_Name)
{
	$.ajax({
		url: "get_proto.html",
		type: "GET",
		data: { proto_Name : proto_Name
		      },
		contentType: "application/json; charset=utf-8",
		success: function (response) {
				actProto(response,proto_Name);
		},
		error: function () {
            console.log("Error - while updating Protocol :"+proto_Name)
		}
	});
};

//*******************************************
// set color for missing values
//*******************************************
function setColor2White(_elemtenID)
{
 document.getElementById(_elemtenID).style.background = "white"
}

//***********************************************
// set color to white by restart creating YAML
//***********************************************
function setColor2WhiteForAll()
{
myInputs=document.getElementsByTagName("INPUT");
for (i = 0; i < myInputs.length; i++)
  {
    myInputs[i].style.backgroundColor = "white";
  } 
}

//*******************************************
// GetValues for Credentials
//*******************************************

function GetValueFromID(ID)
{
myValue = document.getElementById(ID).value
      if (myValue == "")
        {
          myError = true
          document.getElementById(ID).style.background = "red"
        }
 return myValue
}
//*******************************************
// Button Handler CreateYaml
//*******************************************

function CreateYaml()
{
setColor2WhiteForAll()
// Definition for Alexa-Response
 CrLf = '\n'
 indent = "    "
 YAML = "$ItemName:" + CrLf
 YAML +=indent + "alexa_description: $description" + CrLf
 YAML +=indent + "alexa_name: $alexa_name" + CrLf
 YAML +=indent + "alexa_device: $alexa_device" + CrLf
 YAML +=indent + "alexa_auth_cred: '$cam_credentials'" + CrLf
 YAML +=indent + "alexa_icon: CAMERA" + CrLf
 YAML +=indent + "alexa_actions: InitializeCameraStreams" + CrLf
 YAML +=indent + "alexa_camera_imageUri: $Image_Uri " + CrLf
 YAML +=indent + "alexa_csc_proxy_uri: $proxy_Url" + ":443" + CrLf
 YAML +=indent + "alexa_proxy_credentials: '$proxy_credentials'"

// Definition for Stream
 myStream = '{ "protocols":["$protocol"], "resolutions":[{"width":$width,"height":$height}], "authorizationTypes":["$authorization"], "videoCodecs":["$video"], "audioCodecs":["$audio"] }'

// Defintion for URL's
 myUrl = 'Stream#:$Stream_IP'
 myStreamURLs = indent + 'alexa_csc_uri: "$Stream_URLs"'+ CrLf

 // Get Values from WebPage
 if (document.getElementById("enable_stream_1").checked != true)
    {
      alert("You have to activate minimum one stream")
      return
    }

 Values2Replace =         {
                            '$ItemName':'Cam_Name',
                            '$description':'Alexa_Description',
                            '$alexa_name':'Alexa_Name',
                            '$alexa_device':'Alexa_Device',
                            '$Image_Uri':'Image_Url',
                            '$proxy_Url':'Proxy_Url',
                            '$credentials':'user'
                          }

 Stream2Replace =         {
                            '$width':'width_#',
                            '$height':'height_#'
                          }

 StreamSelect2Replace =   { 
                            '$video':'video_#',
                            '$audio':'audio_#',
                            '$authorization':'authorization_#',
                            '$protocol':'protocol_#'
                          }


myStreamUrls         =    {}

myError = false


// Create Credentials

myCamUser = GetValueFromID("user_cam")
myCamPwd  = GetValueFromID("pwd_cam")
cam_Credentials = String(btoa(myCamUser+":"+myCamPwd))
YAML = YAML.replace("$cam_credentials", cam_Credentials)


myProxyUser = GetValueFromID("user")
myProxyPwd = GetValueFromID("pwd")
proxy_Credentials = String(btoa(myProxyUser+":"+myProxyPwd))
YAML = YAML.replace("$proxy_credentials", proxy_Credentials)



for ( var key in Values2Replace)
 {
    if (Values2Replace.hasOwnProperty(key))
     {
      myValue = document.getElementById(Values2Replace[key]).value
      if (myValue == "")
        {
          myError = true
          document.getElementById(Values2Replace[key]).style.background = "red"
        }
      YAML = YAML.replace(key, myValue)
     }
 }


 for ( i=1; i <=3; i++)
    {
      myNewStream = myStream
      myNewStream = myNewStream.replace('#', String(i))
      // Skip not enabled Streams
      if (document.getElementById("enable_stream_"+String(i)).checked == true)
        {
          // Create Stream-String
          console.log("Got info to setup Streamstring for : "+ String(i))
           for ( var key in Stream2Replace)
             {
                if (myNewStream.hasOwnProperty(key))
                 {
                  myValue = document.getElementById(Stream2Replace[key]).value
                  if (myValue == "")
                    {
                      myError = true
                      document.getElementById(Stream2Replace[key]).style.background = "red"
                    }
                  myNewStream = myNewStream.replace(key, myValue)
                 }
             }
           // Now the Select-Boxes
           myNewStreamSelect2Replace = StreamSelect2Replace
           myNewStream = myStream
           myNewStreamSelect2Replace = JSON.parse(JSON.stringify(myNewStreamSelect2Replace).split('#').join(String(i)))
           for ( var key in myNewStreamSelect2Replace)
             {
                if (myNewStreamSelect2Replace.hasOwnProperty(key))
                 {
                  myValue = document.getElementById(myNewStreamSelect2Replace[key]).value

                  myNewStream = myNewStream.replace(key, myValue)
                 }
             }
           console.log(myNewStream)
           // Now the Settings for Resolution
           myNewResulotion2Replace = Stream2Replace
           myNewResulotion2Replace = JSON.parse(JSON.stringify(myNewResulotion2Replace).split('#').join(String(i)))
           for ( var key in myNewResulotion2Replace)
             {
                if (Stream2Replace.hasOwnProperty(key))
                 {
                  myValue = document.getElementById(myNewResulotion2Replace[key]).value
                  if (myValue == "")
                    {
                      myError = true
                      document.getElementById(myNewResulotion2Replace[key]).style.background = "red"
                    }
                  myNewStream = myNewStream.replace(key, myValue)
                 }
             }
            YAML += CrLf + indent + "alexa_stream_"+String(i) + ": "+ "'" + myNewStream +"'"
          // Now Get the Url for this Stream
          myValue = document.getElementById("real_IP_"+String(i)).value
          if (myValue == "")
            {
              myError = true
              document.getElementById("real_IP_"+String(i)).style.background = "red"
            }
          myStreamUrls["Stream"+String(i)]=myValue
        }
    }
 YAML += CrLf + indent + "alexa_csc_uri: "+"'"+JSON.stringify(myStreamUrls)+"'"
 if (myError == true)
  {
    alert("Some Values are missing \r\n See red Fields")
    return
  }

 yaml_resultCodeMirror.setValue(YAML)

}


