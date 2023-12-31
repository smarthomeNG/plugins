var selectedDevice;


//***************************************************
//Function to store manual inserted cookie - File
//***************************************************
function BtnStoreCookie()
{
	data = myCodeMirrorConf.getValue()
	data=JSON.stringify(data)
	data = data.split('\"').join("")
	$.ajax({
		url: "storecookie.html",
		type: "GET",
		data: { cookie_txt : data }, //data,
		contentType: "application/json; charset=utf-8",
		success: function (response) {
			myResult=JSON.parse(response)
			if (myResult.data.Result == true)
				{
				document.getElementById('reloadPage').style.visibility='visible'
				document.getElementById('txt_Result').textContent='You did it\nLogin was successfull\nCookie was stored\nPlease reload Page'
				document.getElementById('txt_Result').style.backgroundColor="Lightgreen"
				document.getElementById('txt_Result').style.color='black'
				}
			else
				{
				document.getElementById('txt_Result').textContent='Sorry, login was not successfull\nCookie was not stored\nPlease try again'
				document.getElementById('txt_Result').style.backgroundColor="Red"
				document.getElementById('txt_Result').style.color='black'
				}
		},
		error: function (xhr, status, error) {
			document.getElementById("txt_Result").innerHTML = "Error while Communication !";
            $("#reload-element").removeClass("fa-spin");
            $("#MFAcardOverlay").hide();
		}
	});	
}


//***************************************************
// Function to communicate with the plugin himself
//***************************************************
function PublicAjax(url, data)
{
	//data = unescape(encodeURIComponent(JSON.stringify(data)))
	data=JSON.stringify(data)
	$.ajax({
		url: url + ".html",
		type: "GET",
		data: { data : data }, //data,
		contentType: "application/json; charset=utf-8",
		success: function (response) {
				ValidateMFAResponse(response);
		},
		error: function (xhr, status, error) {
			document.getElementById("Tooltip").innerHTML= "<div><strong>Error</strong><br><br>Error while Communication !</div>"
		    document.getElementById("Tooltip").style.backgroundColor="red"
	    	 
			
			$("#reload-element").removeClass("fa-spin");
            $("#MFAcardOverlay").hide();
		}
	});	
}

//***************************************************
// Validate the response from Step by Step MFA-Setup
//***************************************************
function ValidateMFAResponse(response)
{
	myData = JSON.parse(response)
	if (myData.Status == 'OK')
		{
		 document.getElementById("Tooltip").style.backgroundColor="#d4edda" 
		 myStep = parseInt(myData.Step.substr(4,1))
		 document.getElementById("Status_" + String(+myStep)).classList.add("fa-check-circle")
		 document.getElementById("Status_" + String(+myStep)).classList.remove("fa-exclamation-triangle")
		 document.getElementById("Status_" + String(+myStep)).style.color = "green"
	     switch (myStep)
	     {
	     case 1:
	    	 {
	    	   myToolTip = "<div>"
	    	   myToolTip +=  "<strong>open Amazon-Site and create a new APP</strong><br><br>"
		       myToolTip +=  "- Amazon-Web-Site will be opened automatically by pressing the button<br>"
			   myToolTip +=  "- Create a new APP<br>"		    	   
	    	   myToolTip +=  '- Select <strong>"barcode could not be read"</strong> and copy the shown MFA-Secret to to clipboard.<br>'
	    	   myToolTip +=  "<br>Press the button to continue"
	    	   myToolTip +=  "</div>"
	    	   document.getElementById("Tooltip").innerHTML= myToolTip
	    	   break;
	    	 }
	     case 2:
	    	 {
	    	   myToolTip = "<div>"
	    	   myToolTip +=  "<strong>Insert the MFA-Secret</strong><br>"
	    	   myToolTip += "- Insert the copied MFA-Secret to the AlexaRc4shNG-Web-Interface<br>"
	    	   myToolTip += '- After you have inserted the copied MFA-Secret, by pressing the button „Code berechnen“ the OTP-Code will be calculated by the plugin.<br>'
   	    	   myToolTip += "<br>Press the button to continue"
	    	   myToolTip += "</div>"
	    	   document.getElementById("Tooltip").innerHTML= myToolTip
	    	   break;
	    	 }	    	 
	     case 3:
	    	 {
	    	   myToolTip = "<div>"
    		   myToolTip += "- The calculated Code will be shown on the Web-Interface and automatically copied to the Clipboard.<br>"
   	       	   myToolTip += "- Please insert the OTP-code to the amazon-site, when the OTP is accepted please confirm.<br>"
   			   myToolTip += " <strong>(you need two tries to insert it from clipboard, on first try the amazon-Website would not accept the code from clipboard</strong>)<br>"
	    	   myToolTip += "<br>Press the button to continue"
	    	   myToolTip += "</div>"
	    	   document.getElementById("Tooltip").innerHTML= myToolTip
	    	   document.getElementById("txtOTP").value= myData.data.OTPCode
	    	   copyToClipboard(myData.data.OTPCode);
	    	   break;
	    	 }	    	 
	     case 4:
	    	 {
	    	   myToolTip = "<div>"
    		   myToolTip +=  "<strong>Store the MFA-Code to your ./etc/plugin.yaml</strong><br>"
	    	   myToolTip += "<br>Press the button to continue"
	    	   myToolTip += "</div>"
	    	   document.getElementById("Tooltip").innerHTML= myToolTip
	    	   break;
	    	 }	    	 
	     case 5:
	    	 {
	    	   myToolTip = "<div>"
	    	   myToolTip +=  "<strong>try to  login with MFA</strong><br>"
	    	   myToolTip += "<br>Press the button to continue"
	    	   myToolTip += "</div>"
	    	   document.getElementById("Tooltip").innerHTML= myToolTip
	    	   break;
	    	 }
	     case 6:
	    	 {
	    	   document.getElementById("Status_" + String(+myStep+1)).classList.add("fa-check-circle")
			   document.getElementById("Status_" + String(+myStep+1)).classList.remove("fa-exclamation-triangle")
			   document.getElementById("Status_" + String(+myStep+1)).style.color = "green"
			   document.getElementById("Status_" + String(+myStep+1)+"_1").classList.add("fa-check-circle")
			   document.getElementById("Status_" + String(+myStep+1)+"_1").classList.remove("fa-exclamation-triangle")
			   document.getElementById("Status_" + String(+myStep+1)+"_1").style.color = "green"
						 
	    	   myToolTip = "<div>"
	    	   myToolTip +=  "<strong>Successfully done</strong><br>"
	    	   myToolTip += "<br>Press the reload button to continue"
	    	   myToolTip += "</div>"
	    	   document.getElementById("Tooltip").innerHTML= myToolTip
	    	   document.getElementById('goal').innerHTML="congratulations<br>You did it !"
    		   document.getElementById('img_goal').src="static/img/alexa_cookie_good.png"
 			   document.getElementsByTagName("img")[0].src="static/img/alexa_cookie_good.png"
 			   document.getElementById('btnMfaReset').style.visibility="hidden"
 			   document.getElementById('btnMfaReload').style.visibility="visible" 				   
	    	   break;
	    	 }
	     }
		 myStep += 1
		 try
		 { document.getElementById("Line_" + String(+myStep)).style.visibility = "visible" }
		 catch (e)
		 {}
		 
		}
	else
		{
		 myStep = parseInt(myData.Step.substr(4,1))
		 document.getElementById("Status_" + String(+myStep)).classList.remove("fa-check-circle")
		 document.getElementById("Status_" + String(+myStep)).classList.add("fa-exclamation-triangle")
		 document.getElementById("Status_" + String(+myStep)).style.color = "red"
	     switch (myStep)
		     {
		     case 3:
		    	 {
		    	 myToolTip = "<div>"
				 myToolTip += "<strong>Error</strong><br>"
			     myToolTip += "<br>"+myData.data.Message
				 myToolTip += "<br>Please reload page"
				 myToolTip += "</div>"
				 document.getElementById("Tooltip").innerHTML= myToolTip
				 document.getElementById("Tooltip").style.backgroundColor="red"
		    	 break;
		    	 }
		     case 5:
	    	 {
		    	 myToolTip = "<div>"
				 myToolTip += "<strong>Error</strong><br>"
			     myToolTip += "<br>"+myData.data.Message
				 myToolTip += "<br>Please reload page"
				 myToolTip += "</div>"
				 document.getElementById("Tooltip").innerHTML= myToolTip
				 document.getElementById("Tooltip").style.backgroundColor="red"
		    	 break;
	    	 }		    	 
		     case 6:
		    	 {
		    	 myStep += 1
		    	 document.getElementById("Status_" + String(+myStep)+"_1").classList.remove("fa-check-circle")
				 document.getElementById("Status_" + String(+myStep)+"_1").classList.add("fa-exclamation-triangle")
				 document.getElementById("Status_" + String(+myStep)+"_1").style.color = "red"
				 document.getElementById('img_goal').src="static/img/alexa_cookie_bad.png"
				 document.getElementsByTagName("img")[0].src="static/img/alexa_cookie_bad.png"
				 document.getElementById('goal').innerHTML="Sorry, login was not successfull"
				 document.getElementById('btnMfaReset').style.visibility="visible"
				 document.getElementById('btnMfaReload').style.visibility="hidden"
				 myToolTip = "<div>"
			     myToolTip +=  "<strong>Please try again</strong><br>"
			     myToolTip += "<br>Press the reset button to continue"
			     myToolTip += "</div>"
			     document.getElementById("Tooltip").innerHTML= myToolTip
			     document.getElementById("Line_" + String(+myStep)).style.visibility = "visible"
		    	 }
	    	 }
		}
	console.log(response)
	$("#reload-element").removeClass("fa-spin")
    $("#MFAcardOverlay").hide();
}

//*******************************************
// MFA-Login Reset
//*******************************************
function mfaReset()
{
	for (var i = 2; i <= 7; i++)
		{
		 document.getElementById("Line_" + String(+i)).style.visibility = "hidden"
		 document.getElementById("Status_" + String(i-1)).classList.remove("fa-check-circle")
		 document.getElementById("Status_" + String(i-1)).classList.remove("fa-exclamation-triangle")
		}
	document.getElementById('btnMfaReset').style.visibility="hidden"
	myToolTip = "<div>"
	myToolTip +=  "<strong>Enter Credentials</strong><br>"
	myToolTip += "Enter your credentials for the alexa.amazon-Website<br>Press the button to continue"
	myToolTip += "</div>"
	document.getElementById("Tooltip").innerHTML= myToolTip
	document.getElementById("txtMFAUser").value = ""
	document.getElementById("txtMFAPwd").value = ""
	document.getElementById("txtMFA").value = ""
	     
		
}
//*******************************************
// Step by Step-Handler MFA-Login
//*******************************************
function BtnHandleMFA(step)
{
    //$("#MFAcardOverlay").addClass("fa-spin");
    $("#MFAcardOverlay").show();
    $("#reload-element").addClass("fa-spin")
	data = {}
  switch(step)
  {
  case 1:
	  {
	  myUser = document.getElementById("txtMFAUser").value
	  myPwd  = document.getElementById("txtMFAPwd").value 
	  data["Key"] ="Step"+String(step); 
	  data["data"]={User: myUser, Pwd:myPwd};
	  PublicAjax('handle_mfa', data, step)
	  break;
	  }
  case 2:
	  {
	  data["data"]={}
	  data["Step"] = "Step2"
	  data["Status"]="OK";
	  myChildWindows = window.open('https://www.amazon.de/a/settings/approval', '_blank', 'location=yes,scrollbars=yes,status=yes');
	  ValidateMFAResponse(JSON.stringify(data));
	  break;
	  }
  case 3:
	  {
	  data["Key"] ="Step"+String(step); 
	  myMFA = document.getElementById("txtMFA").value;
	  data["data"]={MFA: myMFA}
	  PublicAjax('handle_mfa', data, step)
	  break
	  }
  case 4:
	  {
	  data["data"]={}
	  data["Step"] = "Step4"
	  data["Status"]="OK";
	  ValidateMFAResponse(JSON.stringify(data));
	  break
	  }
  case 5:
	  {
	  myUser = document.getElementById("txtMFAUser").value
	  myPwd  = document.getElementById("txtMFAPwd").value
	  myMFA = document.getElementById("txtMFA").value;
	  data["Key"] ="Step"+String(step); 
	  data["data"]={User: myUser, Pwd:myPwd,MFA: myMFA };
	  PublicAjax('handle_mfa', data, step)
	  break;
	  }
  case 6:
	  {
	  data["Key"] ="Step"+String(step); 
	  data["data"]={command: 'login' };
	  PublicAjax('handle_mfa', data, step)
	  break;
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
      mfa = ""
      store2config = true
      encoded=user+":"+pwd;
      encoded=btoa(encoded);
	$.ajax({
		url: "store_credentials.html",
		type: "GET",
		data: { encoded : encoded,
			user : user,
		   	pwd : pwd,
			store_2_config : store2config,
			mfa : mfa,
			login : true
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
// Button Handler LogIn to Amazon-Site
//*******************************************

function BtnLogIn(result)
{
	$.ajax({
		url: "log_in.html",
		type: "GET",
		data: {} ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {
			ValidateLoginResponse(response);
		},
		error: function () {
			document.getElementById("txt_Result").innerHTML = "Error while Communication !";
		}
	});
  return
}

//*******************************************
// Button Handler LogOff from Amazon-Site
//*******************************************

function BtnLogOff(result)
{
	$.ajax({
		url: "log_off.html",
		type: "GET",
		data: {} ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {
			document.getElementById("txt_Result").innerHTML = response;
		},
		error: function () {
			document.getElementById("txt_Result").innerHTML = "Error while Communication !";
		}
	});
  return
}

//*******************************************
// Button Handler for saving Commandlet
//*******************************************

function BtnSave(result)
{
    document.getElementById("txtresult").value = "";


    if (document.getElementById("txtCmdName").value == "")
	{
 	  alert ("No Name given for CommandLet, please enter one");
	  return;
	}
    if (document.getElementById("txtApiUrl").value == "")
	{
 	  alert ("No API-URL given for CommandLet, please enter one");
	  return;
	}

    document.getElementById("txtButton").value ="BtnSave";

    myPayload = myCodeMirrorPayload.getValue();
    StoreCMD
	(
         document.getElementById("txtValue").value,
         document.getElementById("selectedDevice").value,
         myPayload,
         document.getElementById("txtCmdName").value,
         document.getElementById("txtApiUrl").value,
         document.getElementById("txtDescription").value
	);

}

//*******************************************
// Button Handler for checking Json
//*******************************************

function BtnCheck(result)
{

    document.getElementById("txtButton").value ="BtnCheck";
    try {
	// Block of code to try
	myValue = document.getElementById("txtValue").value
	myPayload = myCodeMirrorPayload.getValue();
	myPayload = myPayload.replace("<mValue>",myValue);
	var myTest = JSON.stringify(JSON.parse(myPayload),null,2)
	myCodeMirrorPayload.setValue(myTest);
	myCodeMirrorPayload.focus;
	myCodeMirrorPayload.setCursor(myCodeMirrorPayload.lineCount(),0);
	document.getElementById("txtresult").value = "JSON-Structure is OK";
	document.getElementById("resultOK").style.visibility="visible";
	document.getElementById("resultNOK").style.visibility="hidden";
	
        }
    catch(err) {
         // Block of code to handle errors
	document.getElementById("txtresult").value = "JSON-Structure is not OK\n"+err;
	document.getElementById("resultOK").style.visibility="hidden";
	document.getElementById("resultNOK").style.visibility="visible";
	} 
}

//*******************************************
// Button Handler for testing
//*******************************************

function BtnTest(result)
{
   selectedDevice = document.getElementById("selectedDevice").value;

    if (selectedDevice == "no Device selected")
	{
 	  alert ("No Device selected for Test, first select one");
	  return;
	}
    txtValue = document.getElementById("txtValue").value;
    if (txtValue == "")
	{
 	  alert ("No Value set to send, please enter value");
	  return;
	}

    document.getElementById("txtButton").value ="BtnTest";
    myPayload = myCodeMirrorPayload.getValue();

    TestCMD
	(
         document.getElementById("txtValue").value,
         document.getElementById("selectedDevice").value,
         myPayload,
         document.getElementById("txtCmdName").value,
         document.getElementById("txtApiUrl").value,
         document.getElementById("txtDescription").value
	);
}

//*******************************************
// Button Handler for deleting
//*******************************************

function BtnDelete(result)
{
    var filetodelete = document.getElementById("txtCmdName").value;
    if (filetodelete == "") {
         alert ("No Command selected to delete, first select one");
         return;
        }
    filetodelete=filetodelete+".cmd";
    var r = confirm("Your really want to delete\n\n"+ filetodelete + "\n\nContinue ?");
    if (r == false) {
        return;
        } 
    document.getElementById("txtButton").value ="BtnDelete";
    DeleteCMD
	(
         document.getElementById("txtValue").value,
         document.getElementById("selectedDevice").value,
         "",
         document.getElementById("txtCmdName").value,
         document.getElementById("txtApiUrl").value,
         document.getElementById("txtDescription").value
	);
}


//*************************************************************
// ValidateLoginResponse -checks the login-button
//*************************************************************

function ValidateLoginResponse(response)
{
var myResult = ""
var temp = ""
var objResponse = JSON.parse(response)
for (x in objResponse)
    {
     temp = temp + objResponse[x]+"\n";
    }

document.getElementById("txt_Result").innerHTML = temp;
}

//*************************************************************
// ValidateEncodeResponse -checks the login-button
//*************************************************************

function ValidateEncodeResponse(response)
{
var myResult = ""
var temp = ""
var objResponse = JSON.parse(response)
for (x in objResponse)
    {
     if (x == "0")
 	{
	  document.getElementById("txtEncoded").value = objResponse[x].substr(8);	  
	}
     else
	{
	  temp = temp + objResponse[x]+"\n";
	}
    }

document.getElementById("txt_Result").value = temp;
}



//*************************************************************
// ValidateResponse - checks the response for button-Actions
//*************************************************************

function ValidateResponse(response)
{
var myResult = ""
var temp = ""
var objResponse = JSON.parse(response)
for (x in objResponse[0])
    {
      if (x == "Status") {
	  myResult = objResponse[0][x];
	}
      else {
          temp = temp + objResponse[0][x]+"\n";
        }
    }

document.getElementById("txtresult").value = temp;
if (myResult == "OK")
{
 document.getElementById("resultOK").style.visibility="visible";
 document.getElementById("resultNOK").style.visibility="hidden";
 reloadCmds();
}
else
{
 document.getElementById("resultOK").style.visibility="hidden";
 document.getElementById("resultNOK").style.visibility="visible";
}

}

//*******************************************
// Function to Test Command-Let
//*******************************************

function TestCMD(txtValue,selectedDevice,txt_payload,txtCmdName,txtApiUrl,txtDescription) {
	$.ajax({
		url: "handle_buttons.html",
		type: "GET",
		data: { txtValue : txtValue,
			selectedDevice:selectedDevice,
			txtButton : "BtnTest",
			txt_payload : txt_payload,
			txtCmdName : txtCmdName,
			txtApiUrl : txtApiUrl,
			txtDescription : txtDescription} ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {
				ValidateResponse(response)
		},
		error: function () {
			document.getElementById("txtresult").value = "Error while Communication !";
			document.getElementById("resultOK").style.visibility="hidden";
			document.getElementById("resultNOK").style.visibility="visible";
		}
	});
  return
}

//*******************************************
// Function to Save Command-Let
//*******************************************

function StoreCMD(txtValue,selectedDevice,txt_payload,txtCmdName,txtApiUrl,txtDescription) {
	$.ajax({
		url: "handle_buttons.html",
		type: "GET",
		data: { txtValue : "",
			selectedDevice:selectedDevice,
			txtButton : "BtnSave",
			txt_payload : txt_payload,
			txtCmdName : txtCmdName,
			txtApiUrl : txtApiUrl,
			txtDescription : txtDescription} ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {
				ValidateResponse(response)
		},
		error: function () {
			document.getElementById("txtresult").value = "Error while Communication !";
			document.getElementById("resultOK").style.visibility="hidden";
			document.getElementById("resultNOK").style.visibility="visible";
		}
	});
  return
}

//*******************************************
// Function to Delete Command-Let
//*******************************************

function DeleteCMD(txtValue,selectedDevice,txt_payload,txtCmdName,txtApiUrl,txtDescription) {
	$.ajax({
		url: "handle_buttons.html",
		type: "GET",
		data: { txtValue : "",
			selectedDevice:selectedDevice,
			txtButton : "BtnDelete",
			txt_payload : txt_payload,
			txtCmdName : txtCmdName,
			txtApiUrl : txtApiUrl,
			txtDescription : txtDescription} ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {
				ValidateResponse(response)
		},
		error: function () {
			document.getElementById("txtresult").value = "Error while Communication !";
			document.getElementById("resultOK").style.visibility="hidden";
			document.getElementById("resultNOK").style.visibility="visible";
		}
	});
  return
}


//************************************************
// OnClick-function for Command-List
//************************************************

function SelectCmd()
{

//$("#AlexaDevices").on("click", "tr",function()
  
   var value = $(this).closest("tr").find("td").first().text();

   if (value != "") {
	alert(value);
      }
  
}

//************************************************
// builds and show table with saves Commandlets
//************************************************


function build_cmd_list(result)
{

    var temp ="";
    temp = "<div class='table-responsive' id='tableCommands' href='#' onclick='SelectCmd()'  style=min-width: 30px;><table class='table table-striped table-hover'>";
    temp = temp + "<thead><tr class='shng_heading'><th class='py-1'>Command-Name</th></tr></thead>";
    temp = temp + "<tbody>";
	
    $.each(result, function(index, element) {
        temp = temp + "<a href='SelectListItem'><tr><td class='py-1'>"+ element.Name + "</td></tr>";
    	        
    })
    temp = temp + "</tbody></table></div>";
    $('#Cmds').html(temp);

    $('#tableCommands').on("click", "tr",function()
     {
       var value = $(this).closest("tr").find("td").first().text();
       if (value != "") {
       LoadCommand(value);
     }
    });



}


//*******************************************
// reloads the list with the Command-Lets
//*******************************************

function reloadCmds()
{
        $("#reload-element").addClass("fa-spin");
        $("#cardOverlay").show();
        $.getJSON("build_cmd_list_html", function(result)
        		{
	        	build_cmd_list(result);
	            window.setTimeout(function()
	            		{
		                $("#refresh-element").removeClass("fa-spin");
		                $("#reload-element").removeClass("fa-spin");
		                $("#cardOverlay").hide();
	            		}, 300);

        		});
    
}

//*******************************************
// Load Commandlet to Web-Site
//*******************************************
function LoadCommand(txtCmdName)
{
	$.ajax({
		url: "handle_buttons.html",
		type: "GET",
		data: { txtValue : "",
			selectedDevice:"",
			txtButton : "BtnLoad",
			txt_payload : "",
			txtCmdName : txtCmdName,
			txtApiUrl : "",
			txtDescription : ""} ,
		contentType: "application/json; charset=utf-8",
		success: function (response) {
				ShowCommand(response,txtCmdName);
		},
		error: function () {
			document.getElementById("txtresult").value = "Error while Communication !";
			document.getElementById("resultOK").style.visibility="hidden";
			document.getElementById("resultNOK").style.visibility="visible";
		}
	});
  return
}

//*******************************************
// Load 2 Fields
//*******************************************
function ShowCommand(response,txtCmdName)
{
	var myResult = ""
	var temp = ""
	var objResponse = JSON.parse(response)
  	document.getElementById("txtCmdName").value = txtCmdName;		
	for (x in objResponse[0])
	    {
	      if (x == "Status")
		{
		  myResult = objResponse[0][x];
		}
	     else if (x == "Description")
 		{
		 console.log(objResponse[0][x])
		 var test = objResponse[0][x];

	  	 document.getElementById("txtDescription").value = objResponse[0][x];		
		}
	     else if (x == "myUrl")
		{
		 console.log(objResponse[0][x])
	  	 document.getElementById("txtApiUrl").value = objResponse[0][x];		
		}
	     else if (x == "payload")
		{
		 myjson = objResponse[0][x].split("'").join("\"");
		 myjson = myjson.split("\\").join("");
		 var myTest = JSON.stringify(JSON.parse(myjson),null,2)
 	   myCodeMirrorPayload.setValue(myTest);
	   myCodeMirrorPayload.focus;
		 myCodeMirrorPayload.setCursor(myCodeMirrorPayload.lineCount(),0);
		}
	    }
	document.getElementById("txtresult").value = myResult;
	if (myResult == "OK")
	{
	 document.getElementById("resultOK").style.visibility="visible";
	 document.getElementById("resultNOK").style.visibility="hidden";
	 reloadCmds();
	}
	else
	{
	 document.getElementById("resultOK").style.visibility="hidden";
	 document.getElementById("resultNOK").style.visibility="visible";
	}
}


//************************************************************************
//copyToClipboard - copies the finalized Widget to the Clipboard
//************************************************************************
const copyToClipboard = str => {
	  const el = document.createElement('textarea');  // Create a <textarea>
														// element
	  el.value = str;                                 // Set its value to the
														// string that you want
														// copied
	  el.setAttribute('readonly', '');                // Make it readonly to
														// be tamper-proof
	  el.style.position = 'absolute';                 
	  el.style.left = '-9999px';                      // Move outside the
														// screen to make it
														// invisible
	  document.body.appendChild(el);                  // Append the <textarea>
														// element to the HTML
														// document
	  const selected =            
	    document.getSelection().rangeCount > 0        // Check if there is any
														// content selected
														// previously
	      ? document.getSelection().getRangeAt(0)     // Store selection if
														// found
	      : false;                                    // Mark as false to know
														// no selection existed
														// before
	  el.select();                                    // Select the <textarea>
														// content
	  document.execCommand('copy');                   // Copy - only works as
														// a result of a user
														// action (e.g. click
														// events)
	  document.body.removeChild(el);                  // Remove the <textarea>
														// element
	  if (selected) {                                 // If a selection
														// existed before
														// copying
	    document.getSelection().removeAllRanges();    // Unselect everything
														// on the HTML document
	    document.getSelection().addRange(selected);   // Restore the original
														// selection
	  }
	};
