//*************************************************************
// check Auto-Updates for protocols
//*************************************************************
setInterval(Checkupdate4Protocolls, 5000);

//*************************************************************
// set Location
//*************************************************************

function BtnStoreLocation()
{
 myLongitude = document.getElementById("txtlongitude").value
 myLatitude  = document.getElementById("txtlatitude").value
 $.ajax({
    url: "set_location.html",
    type: "GET",
    data: { longitude : myLongitude,
            latitude  : myLatitude
          },
    contentType: "application/json; charset=utf-8",
    success: function (response) {
		     document.getElementById("txt_LocationResult").innerHTML = response;
    },
    error: function () {
        document.getElementById("txt_LocationResult").innerHTML = "Error while communication";
        console.log("Error - while setting location :")
    }
 });
};

//*************************************************************
// delete Protocols
//*************************************************************

function DeleteProto(btn_Name)
{
  if (btn_Name =="btn_clear_proto_commun")
    { proto_Name = "webif.communication_protocoll"}
  else if (btn_Name == "btn_clear_proto_states")
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

    if (proto_Name == 'webif.communication_protocoll')
    {
        logCodeMirror.setValue("")
    }
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
    commun_checked = document.getElementById("proto_commun_check").checked
    if (states_checked == true)
    {
     UpdateProto('state_log_file')
    }
    if (commun_checked == true)
    {
     UpdateProto('Com_log_file')
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
    if (proto_Name == 'Com_log_file')
    {
        logCodeMirror.setValue(myText)
    }
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




//*************************************************************
// ValidateEncodeResponse -checks the login-button
//*************************************************************

function ValidateEncodeResponse(response)
{
var myResult = ""
var temp = ""
var objResponse = JSON.parse(response)
for (x in objResponse.Proto)
    {
      temp = temp + objResponse.Proto[x]+"\n";
    }

document.getElementById("txt_Result").value = temp;
document.getElementById("txtEncoded").innerHTML = objResponse.Params.encoded
document.getElementById("text_session_id").innerHTML = objResponse.Params.SessionID
document.getElementById("text_experitation").innerHTML = objResponse.Params.timeStamp

if (document.getElementById("store_2_config").checked = true)
{
    if (objResponse.Params.logged_in == true)
        {
         document.getElementById("grafic_logged_in").src = "static/img/lamp_green.png"
         document.getElementById("text_logged_in").innerHTML = "logged in"

        }
    else
        {
         document.getElementById("grafic_logged_in").src = "static/img/lamp_red.png"
         document.getElementById("text_logged_in").innerHTML = "logged off"
        }
 }
}

//*******************************************
// Button Handler for Encoding credentials
//*******************************************

function BtnEncode(result)
{
      user = document.getElementById("txtUser").value;
      pwd = document.getElementById("txtPwd").value;
      store2config = document.getElementById("store_2_config").checked;
      encoded=user+":"+pwd;
      encoded=btoa(encoded);
	$.ajax({
		url: "store_credentials.html",
		type: "GET",
		data: { encoded : encoded,
			user : user,
		   	pwd : pwd,
			store_2_config : store2config
		      },
		contentType: "application/json; charset=utf-8",
		success: function (response) {
				ValidateEncodeResponse(response);
		},
		error: function () {
            document.getElementById("txt_Result").innerHTML = "Error while Communication !";
		}
	});
  return
}

//*******************************************
// Function to Store Color
//*******************************************

function StoreColor(Color) {
	$.ajax({
		url: "store_color.html",
		type: "GET",
		data: { newColor : Color,
              } ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {console.log('OK-setting Colour-Code')},
		error: function () {console.log('error-setting Colour-Code')}
	});
  return
}

//*******************************************
// Function to add_svg_images
//*******************************************

function Store_add_svg(Value) {
	$.ajax({
		url: "store_add_svg.html",
		type: "GET",
		data: { add_svg_str : Value,
              } ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {console.log('OK add_svg_image stored')},
		error: function () {console.log('error-add_svg_image stored')}
	});
  return
}

//*******************************************
// Function to Store State-Trigger-Events
//*******************************************

function StoreStateTrigger(TriggerItem, Value) {
	$.ajax({
		url: "store_state_trigger.html",
		type: "GET",
		data: { Trigger_State_Item : TriggerItem,
                newState : Value
              } ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {console.log('OK-setting Trigger-State')},
		error: function () {console.log('error-setting Trigger-State')}
	});
  return
}

//*******************************************
// Function to Store Alarm-Trigger-Events
//*******************************************

function StoreAlarmTrigger(TriggerItem, Value) {
	$.ajax({
		url: "store_alarm_trigger.html",
		type: "GET",
		data: { Trigger_Alarm_Item : TriggerItem,
                newAlarm : Value
              } ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {console.log('OK-setting Trigger-Alarm')},
		error: function () {console.log('error-setting Trigger-Alarm')}
	});
  return
}

//*******************************************
// Handler for Selecting State-Triggers
//*******************************************

function selectStateTrigger(SelectID)
{
    mySelect = document.getElementById(SelectID)
    myValue = mySelect.options[mySelect.options.selectedIndex].text
    StoreStateTrigger(SelectID, myValue)
}

//*******************************************
// Handler for Selecting Alarm-Triggers
//*******************************************

function selectAlarmTrigger(SelectID)
{
    mySelect = document.getElementById(SelectID)
    myValue = mySelect.value
    StoreAlarmTrigger(SelectID, myValue)
}


//*******************************************
// Button Handler for saving Colour
//*******************************************

function SaveColor(picker)
{
    newColor = picker.toHEXString()
    StoreColor(newColor)
}

