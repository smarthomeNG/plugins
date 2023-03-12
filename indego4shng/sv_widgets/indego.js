// ----------------------------------------------------------------------------
// ---   indego.js   ----------------------------------------------------------
// ----------------------------------------------------------------------------
//
// Indego-Widget für Handling der Indego-Funktionen
//
// Darstellung der Indego-Kalender Einträge  in Form eine Tabelle mit den Einträgen
// Bearbeiten, löschen und speichern von Kalendereinträgen
// Darstellung der Mähspur - aktualisieren der Mäherposition in der Karte
// Handling Wintermode
// Handling 350/400er und 800/1000er Series
//
//
// (c) Andre Kohler		- 2019
//
//
// ----- indego.calendar -------------------------------------------------------

var actCalendar = ""
var orgCalendar = ""
var newCalendar = ""
var mode = ""
var oldKey = ""
var calType = ""

var activeOrgPredictive = 0
var activeOrgCalendar = 0
var activeNewPredictive = 0
var activeNewCalendar = 0

var CalCount = 0
var m_CalCount = 0
var p_CalCount = 0

var activeMode = 0
var MowTrack = ""
var orgMap = ""
var add_svg_images = ""
var mower_colour = "#FFF601"
var actMowerPos = ""

var htmlPopUp = "<div data-role='popup' data-overlay-theme='b' data-theme='a' class='messagePopup' id='uzsuIndegoContent' data-dismissible = 'false' data-history='false' data-position-to='window'>"
		+ "<button data-rel='back' data-icon='delete' data-iconpos='notext' class='ui-btn-right' id='indegoClose'></button>"
		+ "<div class='uzsuPopupHeader id=popHeader'><h5><u>HEADLINE</u><h4></div>"
		+
		// Body
		"<table>"
		+ "<tr>"
		+ "<td width='70px'><FONT SIZE='2'>Uhrzeit von:</td>"
		+ "<td width='60px'>"
		+ "<input type='time' id='t_von' name='Time_von'  min='0:00' max='23:59' required step=600 width=80px>"
		+ "</td>"
		+ "<td width='30px'><FONT SIZE='2'><center>bis:</center></td>"
		+ "<td width='60px'>"
		+ "<input type='time' id='t_bis' name='Time_bis'  min='0:00' max='23:59' required step=600 width=80px>"
		+ "</td>"
		+ "<td></td>"
		+ "</tr><tr>"
		+ "<td colspan='5'></td>"
		+ "</tr>"
		+ "<tr>"
		+ "<td colspan='5' valign='top'"
		+ "<form>"
		+ "<fieldset class='uzsuWeekday ui-controlgroup ui-controlgroup-horizontal ui-corner-all ui-mini' data-role = 'controlgroup' data-type = 'horizontal' id='Weekdays'>"
		+ "<legend><FONT SIZE='2'>Wochentag:</font></legend>"
		+ "<label title='Mo'><input id = 'day_0' checked_0 type='checkbox' value='0'>Mo</label>"
		+ "<label title='Di'><input id = 'day_1' checked_1 type='checkbox' value='1'>Di</label>"
		+ "<label title='Mi'><input id = 'day_2' checked_2 type='checkbox' value='2'>Mi</label>"
		+ "<label title='Do'><input id = 'day_3' checked_3 type='checkbox' value='3'>Do</label>"
		+ "<label title='Fr'><input id = 'day_4' checked_4 type='checkbox' value='4'>Fr</label>"
		+ "<label title='Sa'><input id = 'day_5' checked_5 type='checkbox' value='5'>Sa</label>"
		+ "<label title='So'><input id = 'day_6' checked_6 type='checkbox' value='6'>So</label>"
		+ "</fieldset>"
		+ "</form>"
		+ "</div>"
		+ "</div>"
		+ "</td>"
		+ "</tr>"
		+ "</table>"
		+
		// Footer
		"<div class='uzsuTableFooter'>"
		+ "<div class='uzsuRowFooter'>"
		+ "<span style='float:right'>"
		+ "<div class='uzsuCell' style='float: right'>"
		+ "<div data-role='controlgroup' data-type='horizontal' data-inline='true' data-mini='true'>"
		+ "<button id='indegoCancel'>"
		+ sv_lang.uzsu.cancel
		+ "</button>"
		+ "<button id='indegoSave'>"
		+ sv_lang.uzsu.ok
		+ "</button>"
		+ "</div>"
		+ "</div>" + "</span>" + "</div>" +

		"</div>";


//-------------Start - Functions for the Map ------------------------------

function HideMowTrack()
{
	try
	{
		//document.getElementById("mower_track_id").outerHTML = '<g id="mower_track_id"</g>'
		document.getElementById("svg_mower_track").remove()
		if (actMowerPos != "")
		{
			UpdateMowerPos(actMowerPos)
		}
	}
	catch (e)
	{
	console.log("not able to Hide mow_track")
	}
}

function DrawMowTrack(DrawLine)
{
	try
	{
		var svg = document.getElementById("svg_garden_map")
		if (svg == null) { return }
		var newElement = document.createElementNS("http://www.w3.org/2000/svg", 'polyline'); //Create a path in SVG's namespace
		newElement.id = 'svg_mower_track'
		for (key in DrawLine) 
		{
			if (key == 'Points')
			{
				myPoints = DrawLine[key]
				myPoints.forEach(function(element)
				{
					myPoint = element.split(',')
					myNewPoint = svg.createSVGPoint()
					myNewPoint.x = parseInt(myPoint[0])
					myNewPoint.y = parseInt(myPoint[1])
					newElement.points.appendItem(myNewPoint)
				})
			}
			else
			{
				// country.setAttribute("style", "fill: blue; stroke: black");
				newElement.setAttribute("style", DrawLine[key]); //Set path's data
			}
			
		}
		var svg = document.getElementById("mower_track_id")
		svg.appendChild(newElement);
		
		
		if (actMowerPos != "")
		{
			UpdateMowerPos(actMowerPos)
		}
	}
	catch (e)
	{
	console.log("not able to show mow_track")
	}
}

function UpdateMowerPos(actPos)
{
	position = actPos.split(",")
	try
		{
		var mowerObject = document.getElementById('mower_pos');
		mowerObject.setAttribute("cx", position[0]);
		mowerObject.setAttribute("cy", position[1]);
		}
	catch (e)
		{
		console.log("No Mower Position found in Grafic")
		}

}

//-------------End - Functions for the Map ------------------------------




function MessageHandling(click_item) {
	if (click_item == 'alert_read' || click_item == 'alert_delete') {
		myPopup = document.getElementById("rpopupalarm-popup")
		myPopup.classList.remove("ui-popup-active")
		myPopup.classList.add("ui-popup-hidden")
		myCheckBoxes = $(".inedgo_alert_check")
		myAlerts2Handle = []
		for (alertId in myCheckBoxes) {
			if (myCheckBoxes[alertId].checked == true) {
				myAlerts2Handle.push(myCheckBoxes[alertId].id)
			}
		}
		if (myAlerts2Handle.length == 0) {
			return
		}
		if (click_item == 'alert_read') {
			io.write('indego.visu.alerts_set_read', myAlerts2Handle)
		} else if (click_item == 'alert_delete') {
			io.write('indego.visu.alerts_set_clear', myAlerts2Handle)
		}
	}
}

function onClickToggle(myID) {
	if (document.getElementById("ToggleCalender_1").src.search("minus") > 0) {
		document.getElementById('SMW').style.display = 'none'
		document.getElementById("ToggleCalender_1").src = 'icons/ws/jquery_plus.svg'
	} else {
		document.getElementById('SMW').style.display = 'block'
		document.getElementById("ToggleCalender_1").src = 'icons/ws/jquery_minus.svg'
	}

}

function ShowPopUp(calType, myKey) {
	// Append to actual site
	// Headline anpassen
	if (mode == "Edit") {
		PopUp_2_Show = htmlPopUp.replace("HEADLINE", "Kalendereintrag ändern:")
	} else {
		PopUp_2_Show = htmlPopUp.replace("HEADLINE", "Neuer Kalendereintrag:")
	}

	var indegoPopup = $(PopUp_2_Show)
			.appendTo(".indegoadd")
			.enhanceWithin()
			.popup()
			.on(
					{
						popupbeforeposition : function(ev, ui) {
							var maxHeight = $(window).height() - 230; // 180
							document.getElementById("uzsuIndegoContent-popup").style.width = "400px"
						},
						popupafteropen : function(ev, ui) {
							$(this).popup('reposition', {
								y : 30
							})
						},
						popupafterclose : function(ev, ui) {
							$(indegoPopup).remove();
							$(window).off('resize', self._onresize);
						}
					});

	// Fill values on Edit-Mode
	if (mode == "Edit") {
		if (calType == 'm') {
			myObj = newCalendar[0][myKey]
		} else {
			myObj = newPredictiveCalendar[0][myKey]
		}

		document.getElementById("t_von").value = myObj.Start
		document.getElementById("t_bis").value = myObj.End
		i = 0
		while (i <= 6) {
			actDay = "day_" + String(i)

			if (myObj.Days.search(String(i)) != -1) {
				document.getElementById(actDay).checked = true
				$('#' + actDay).prop('checked', true);
				$("#" + actDay).checkboxradio("refresh")
			} else {
				document.getElementById(actDay).checked = false
				$('#' + actDay).prop('checked', false);
				$("#" + actDay).checkboxradio("refresh")
			}

			i += 1
		}

	}

	// Close Popup by X or cancel
	indegoPopup.find('#indegoClose, #indegoCancel').bind('click', function(e) {
		indegoPopup.popup('close');
	});

	// save Values by OK
	indegoPopup.find('#indegoSave').bind('click', function(e) {
		CloseEntryWindowByOK()
		indegoPopup.popup('close');
	});

	// Popup zeigen
	indegoPopup.popup('open');// .css({ position: 'fixed', top: '30px' });
}

/*
function EnableCalendar(calType) {
	return

	

	if (calType == 'M') {

		CalCount = m_CalCount
	} else {
		CalCount = p_CalCount
	}
	var FirstDay = 5
	for (actCal in CalCount) {
		var strActCal = CalCount[actCal]
		if (CalCount.length > 1) {
			if (strActCal < FirstDay) {
				FirstDay = strActCal
			}
			// Show labels for transmitted Calendars
			var strCaption = calType + '-caption_cal_' + strActCal
			document.getElementById(strCaption).style.display = "block"
		}
	}
	var firstDay2Show = calType + "-caption_cal_" + FirstDay
	document.getElementById(firstDay2Show).classList.add("ui-first-child")

	if (CalCount.length == 1) {
		var strActCal = CalCount[0]
		var strCaption = calType + '-caption_cal_6'
		document.getElementById(strCaption).style.display = "block"
		document.getElementById(strCaption).value = CalCount[0]
	}
}
*/
function DrawCalendar(TableName, CalNo, preFix) {
	if (preFix == "m") {
		$("#indego-draw-calendar-2-act").html("")
	}

	var myDays = [ "Mo", "Di", "Mi", "Do", "Fr", "Sa", "So" ]
	d = 0
	myHtml = ""
	h = 0
	myHtml += "<tr>"
	myHtml += "<th></th>"
	while (h <= 23) {
		myHtml += "<th width=5px height=10px style='border:1px solid #000000;border-collapse: collapse;'>"
				+ String(h)
		myHtml += "</th>"
		h += 1
	}
	myHtml += "</tr>"
	while (d <= 6) {
		myHtml += "<tr>"
		myHtml += "<td width=5px height=10px style='border:1px solid #000000;border-collapse: collapse'>"
				+ myDays[d] + "</td>"
		h = 0
		while (h <= 23) {
			myHtml += "<td id="
					+ preFix
					+ '-'
					+ CalNo
					+ "-"
					+ String(d)
					+ "-"
					+ String(h)
					+ " width=5px height=10px style='border:1px solid #000000;border-collapse: collapse'>"
			myHtml += "</td>"
			h += 1
		}
		myHtml += "</tr>"
		d += 1
	}
	try {
		$("#" + TableName).html(myHtml)
	} catch (e) {
		console.log("Fehler")
	}
}

function ReDrawActCalendar(type) {
	if (type == 'M') {
		CalCount = m_CalCount
		activeCalendar = activeNewCalendar
	} else {
		CalCount = p_CalCount
		activeCalendar = activeNewPredictive
	}

	// Create round Corner for ON
	try {
		var activeDay = type + "-caption_cal_6"
		document.getElementById(activeDay).classList.add("ui-first-child")
		var ll_first = false
		i = 0
		while (i <= 6) {
			var activeDay = type + "-cal_" + parseInt(i)
			if (activeCalendar == i) // && i != 0)
			{
				document.getElementById(activeDay).checked = true
			} else {
				document.getElementById(activeDay).checked = false
			}

			$(document.getElementById(activeDay)).checkboxradio("refresh")
			i += 1
		}

		if (CalCount.length == 1 && activeCalendar != "0") {
			var activeDay = type + "-cal_6"
			document.getElementById(activeDay).checked = true
			$(document.getElementById(activeDay)).checkboxradio("refresh")
		}
	} catch (e) {
		console.log("Error")
	}
}

function GetActCalendar(type) {
	i = 0
	while (i <= 6) {
		var activeDay = type + "-cal_" + parseInt(i)
		if (document.getElementById(activeDay).checked == true) {
			if (i == 6) // Spezialfall - nur ein Kalender EIN/AUS
				i = CalCount[0]
			break
		}
		i += 1
	}
	return i
}
function ValidateEntry(CalNo, Days, myStartTime, myEndTime) {
	var msg = ""
	var DayCount = new Array(0, 0, 0, 0, 0, 0, 0)
	var myDays = [ "Montag", "Dienstag", "Mittwocch", "Donnerstag", "Freitag",
			"Samstag", "Sonntag" ]
	i = -1
	while (i < newCalendar.length) {
		i += 1
		calendar = newCalendar[i]
		for ( var key in calendar) {
			if (key.substring(0, 1) != CalNo) {
				continue
			}
			if (calendar.hasOwnProperty(key)) {
				counter = 0
				while (counter <= 6) {
					if (counter = 6) {
						console.log("")
					}
					if (calendar[key].Days.search(String(counter)) != -1
							&& Days.search(String(counter)) != -1) {
						DayCount[counter] += 1
					}
					if (DayCount[counter] >= 2) {
						msg = "Sie haben für " + myDays[counter]
								+ " mehr als zwei Mähzeiten erfasst\r\n"
						msg += "Bitte korrigieren, es sind pro Kalender und Tag nur zwei Mähzeiten vorgesehen\r\n"
						break
					}
					counter += 1
				}
			}
		}

	}
	// Check Times - are they usefull ?
	if (myStartTime >= myEndTime) {
		msg += "\r\nDie Startzeit ist grösser oder gleich der Endzeit, bitte korrigieren\r\n"
	}
	if (Days == "") {
		msg += "Bitte eine Tag wählen"
	}
	return msg
}

function CancelChanges_mow(click_item) {
	newCalendar = $.extend(true, [], orgCalendar);
	UpdateTable(orgCalendar, 'indego-draw-calendar', 'indego-calendar', 'm')

	activeNewCalendar = activeOrgCalendar
	// ReDrawActCalendar('M');
}

function SaveChanges_mow(click_item) {
	// !!!!!!!!!!!!!!!!!
	// Kalender beim speichern unverändert lassen
	// !!!!!!!!!!!!!!!!!
	
	activeNewCalendar = click_item.substring(10, 11)
	// activeNewCalendar = GetActCalendar('M')

	io.write('indego.calendar_sel_cal', activeNewCalendar)
	// activeOrgCalendar = activeNewCalendar

	io.write('indego.calendar_list', newCalendar[0])
	// orgCalendar = $.extend( true, [], newCalendar );
	io.write('indego.calendar_save', true)
}

// Functions for Predictive Calendar
function CancelChanges_pred(click_item) {
	newPredictiveCalendar = $.extend(true, [], orgPredictiveCalendar);
	UpdateTable(orgPredictiveCalendar, 'indego-pred-draw-calendar',
			'indego-pred-calendar', 'p')

	activeNewPredictive = activeOrgPredictive
	// ReDrawActCalendar('P');

}

function SaveChanges_pred(click_item) {
	activeNewPredictive = click_item.substring(20, 21)
	// activeNewPredictive = GetActCalendar('P')
	io.write('indego.calendar_predictive_sel_cal', activeNewPredictive)
	// activeOrgPredictive = activeNewPredictive

	io.write('indego.calendar_predictive_list', newPredictiveCalendar[0])
	// orgPredictiveCalendar = $.extend( true, [], newPredictiveCalendar );
	io.write('indego.calendar_predictive_save', true)
}

function InitWindow() {
	i = 0
	while (i <= 6) {
		actDay = "day_" + String(i)
		$("#" + actDay).prop("checked", false)
		$("#" + actDay).checkboxradio("refresh")
		i += 1
	}
}

// Stores the given values to the list
function CloseEntryWindowByOK() {
	myTest = this

	StartTime = document.getElementById("t_von").value
	EndTime = document.getElementById("t_bis").value
	myKey = actCalendar + "-" + StartTime + "-" + EndTime
	DayArray = ""
	i = 0
	while (i <= 6) {
		actDay = "day_" + String(i)
		DayState = document.getElementById(actDay).checked
		if (DayState == true) {
			if (DayArray.length > 0) {
				DayArray += ","
			}
			DayArray += String(i)
		}
		i += 1
	}
	msg = ValidateEntry(actCalendar, DayArray, StartTime, EndTime)
	if (msg.length != 0) {
		alert(msg)
		return

	}
	console.log("Key :" + myKey + ' DayArray :' + DayArray);
	myEntry = {
		"Days" : DayArray,
		"Start" : StartTime,
		"End" : EndTime,
		"Key" : myKey
	}
	if (mode == "Edit") {
		// Remove the old Key/Value
		if (calType == 'm') {
			delete newCalendar[0][oldKey]
		} else {
			delete newPredictiveCalendar[0][oldKey]
		}
	}
	if (calType == 'm') {
		newCalendar[0][myKey] = myEntry
		UpdateTable(newCalendar, 'indego-draw-calendar', 'indego-calendar',
				calType)
	} else {
		newPredictiveCalendar[0][myKey] = myEntry
		UpdateTable(newPredictiveCalendar, 'indego-pred-draw-calendar',
				'indego-pred-calendar', calType)
	}

}

function BtnEdit(click_item) {
	console.log("BtnEdit from element :" + click_item);
	myKey = click_item.substring(6, 21)
	oldKey = myKey
	actCalendar = click_item.substring(6, 7)
	calType = click_item.substring(0, 1)
	mode = "Edit"
	ShowPopUp(calType, myKey)
}

function BtnDelete(click_item) {
	console.log("BtnDelete from element :" + click_item);
	myKey = click_item.substring(8, 21)
	calType = click_item.substring(0, 1)
	if (calType == 'm') {
		for (var i = 0; i <= 5; i++) {
			try {
				$('#indego-calendar' + '-' + String(i)).html("");
			} catch (e) {
			}
		}
		delete newCalendar[0][myKey]
		UpdateTable(newCalendar, 'indego-draw-calendar', 'indego-calendar',
				calType)
	} else {
		for (var i = 0; i <= 5; i++) {
			try {
				$('#indego-pred-calendar' + '-' + String(i)).html("");
			} catch (e) {
			}
		}
		delete newPredictiveCalendar[0][myKey]
		UpdateTable(newPredictiveCalendar, 'indego-pred-draw-calendar',
				'indego-pred-calendar', calType)
	}

}

function BtnAdd(click_item) {
	console.log("BtnAdd from element :" + click_item);
	// **************************
	actCalendar = click_item.substring(5, 6)
	calType = click_item.substring(0, 1)
	mode = "Add"

	ShowPopUp(calType, '')
}

function FillDrawingCalendar(myCal, myColour, preFix) {
	try {
		i = 0
		while (i < myCal.length) {
			calendar = myCal[i]
			retValTime = ""
			retvalDays = ""
			for ( var key in calendar) {
				if (calendar.hasOwnProperty(key)) {
					if (key == 'Params') {
						continue
					}
					if (calendar[key].hasOwnProperty('Color'))
						{
						colour2Draw = calendar[key]['Color']
						}
					else
						{
						colour2Draw = myColour
						}
					myIndex = parseInt(key[0]) // which Calendar 1/2/3/4/5
					myArray = calendar[key].Days.split(",")
					for (var numberOfEntry = 0; numberOfEntry < myArray.length; numberOfEntry++) {
						actHour = parseFloat(calendar[key].Start
								.substring(0, 2))
						while (actHour <= parseFloat(calendar[key].End
								.substring(0, 2))) {
							if (actHour == parseFloat(calendar[key].End
									.substring(0, 2))
									&& parseFloat(calendar[key].End.substring(
											3, 5)) > 0) {
								myID = preFix + '-' + myIndex + "-"
										+ myArray[numberOfEntry] + "-"
										+ String(actHour)
								myCell = document.getElementById(myID)
								myCell.bgColor = colour2Draw
							} else if (actHour < parseFloat(calendar[key].End
									.substring(0, 2))) {
								myID = preFix + '-' + myIndex + "-"
										+ myArray[numberOfEntry] + "-"
										+ String(actHour)
								myCell = document.getElementById(myID)
								myCell.bgColor = colour2Draw
							}

							actHour += 1
						}
					}
					;
				}
			}
			i += 1
		}
		// Now Copy HTML to act Calender in Modus-Status
		$("#indego-draw-calendar-2-act").html(
				$("#indego-draw-calendar-2").html())

	} catch (e) {
		console.log("Error while drawing Calendar")
	}
}

function UpdateTable(myCal, preFixDrawCalender, preFixEntryCalendar, preFix) {
	var cals2draw = []
	var myTable = new Array(5)
	i = 0

	while (i < myCal.length) {
		calendar = myCal[i]
		retValTime = ""
		retvalDays = ""
		for ( var key in calendar) {
			if (calendar.hasOwnProperty(key)) {
				if (key == 'Params') {
					cals2draw = calendar[key]['CalCount']
					continue
				}
				myIndex = parseInt(key[0])
				retValTime = '<tr><td>' + calendar[key].Start + '-'
						+ calendar[key].End + '</td>';
				retvalDays = '<td>'
				if (calendar[key].Days.search("0") != -1) {
					retvalDays += 'Mo '
				}
				if (calendar[key].Days.search("1") != -1) {
					retvalDays += 'Di '
				}
				if (calendar[key].Days.search("2") != -1) {
					retvalDays += 'Mi '
				}
				if (calendar[key].Days.search("3") != -1) {
					retvalDays += 'Do '
				}
				if (calendar[key].Days.search("4") != -1) {
					retvalDays += 'Fr '
				}
				if (calendar[key].Days.search("5") != -1) {
					retvalDays += 'Sa '
				}
				if (calendar[key].Days.search("6") != -1) {
					retvalDays += 'So'
				}
				retvalDays = retvalDays + '</td>'
				myRow = retValTime + retvalDays
				if (myIndex != 3 || preFix != 'm') {

					editID = preFix + "edit_" + key
					var editButton = "<a id='"
							+ editID
							+ "' class='ui-btn ui-mini ui-corner-all ui-btn-inline' onclick=BtnEdit(this.id)> <img id='img_"
							+ editID
							+ "' class='icon' src='icons/ws/jquery_edit.svg' alt='Edit'></a>"

					deleteID = preFix + "delete_" + key
					var deleteButton = "<a id='"
							+ deleteID
							+ "' class='ui-btn ui-mini ui-corner-all ui-btn-inline ui-nodisc-icon' onclick=BtnDelete(this.id)> <img id='img_"
							+ deleteID
							+ "' class='icon' src='icons/ws/message_garbage.svg' alt='Del'></a>"

					myRow += "<td>"
							+ "<div class='indegoControl' style='float: right'>"
							+ "<div data-role='controlgroup' data-type='horizontal' data-inline='true' data-mini='true'>"
							+ editButton + deleteButton + "</div>" + "</div>"
							+ "</td>" + "</tr>"
				} else {
					myRow += "</tr>"
				}
				console.log(key, calendar[key].Start);
				myTable[myIndex] += myRow
			}
		}
		i += 1
	}
	i = 1
	while (i <= 5) {
		if (i != 3 || preFix != 'm') {
			/*
			 * myTable[i] += "<tr><td colspan='3' style='align: left>'"+ "<div
			 * class='indegoadd'>" + "<div data-role='controlgroup'
			 * data-type='horizontal' data-inline='true' data-mini='true'>" + "<button
			 * id='" +preFix+ "add_"+String(i) + "'
			 * onclick=BtnAdd(this.id)>Eintrag hinzu</button>" + "</div>" + "</div>" + '</td></tr>'
			 */
		}
		i += 1
	}
	i = 1
	// Now draw the calendars
	//while (i <= 8) {
	cals2draw.forEach (function(element){
		i=element
		$('#' + preFixEntryCalendar + '-' + String(i)).html(myTable[i]);
		DrawCalendar(preFixDrawCalender + "-" + String(i), i, preFix)
	})

	// Fill the Drawing Calendars
	// First the Mowing-Calendar
	if (preFix == 'm') {
		Colour = "#0099000"
	} else {
		Colour = "#DC143C"
	}
	FillDrawingCalendar(myCal, Colour, preFix)

}

// ******************************************************
// Widget for Mowing calendar
// ******************************************************
$.widget("sv.indego_calendar", $.sv.widget,
		{

			initSelector : 'div[data-widget="indego.calendar"]',

			_create : function() {
				this._super();
			},

			_update : function(response) {

				// wenn keine Daten vorhanden, dann ist kein item mit den
				// eigenschaften hinterlegt und es wird nichts gemacht
				if (response.length === 0) {
					notify.error("Indego widget", "No Calendar found ");
					return;
				}

				for ( var key in response[0]) {
					if (response[0].hasOwnProperty(key)) {
						if (key = 'Params') {
							m_CalCount = response[0][key]['CalCount']
						}
					}

				}
				if (String(m_CalCount).search("8") == -1)
					{
					orgCalendar = $.extend(true, [], response);
					newCalendar = $.extend(true, [], response);
					//EnableCalendar('M')
					}
				UpdateTable($.extend(true, [], response), 'indego-draw-calendar',
						'indego-calendar', 'm')
				ReDrawActCalendar('M')
			}
		});

// ******************************************************
// Widget for smartMow excluding times calendar
// ******************************************************
$.widget("sv.calendar_predictive_list", $.sv.widget, {

	initSelector : 'div[data-widget="indego.calendar_predictive_list"]',

	_create : function() {
		this._super();
	},

	_update : function(response) {

		// wenn keine Daten vorhanden, dann ist kein item mit den Eigenschaften
		// hinterlegt und es wird nichts gemacht
		if (response.length === 0) {
			notify.error("Indego widget", "No predictive Calendar found ");
			return;
		}

		for ( var key in response[0]) {
			if (response[0].hasOwnProperty(key)) {
				if (key = 'Params') {
					p_CalCount = response[0][key]['CalCount']
				}
			}

		}

		orgPredictiveCalendar = $.extend(true, [], response);
		newPredictiveCalendar = $.extend(true, [], response);

		//EnableCalendar('P')
		UpdateTable(orgPredictiveCalendar, 'indego-pred-draw-calendar',
				'indego-pred-calendar', 'p')
		ReDrawActCalendar('P')

	}
});

// *****************************************************
// Widget for active calendar
// *****************************************************
$.widget("sv.calendar_sel_cal", $.sv.widget, {

	initSelector : 'div[data-widget="indego.calendar_sel_cal"]',
	options : {
		mode : '',
		id : ''
	},

	_create : function() {
		this._super();
		var id = this.options.id;
	},

	_update : function(response) {

		// wenn keine Daten vorhanden, dann ist kein item mit den eigenschaften
		// hinterlegt und es wird nichts gemacht
		if (response.length === 0) {
			notify.error("Indego widget",
					"No active predictive Calendar found ");
			return;
		}

		var type = this.options.mode
		if (type == 'P') {
			activeOrgPredictive = parseInt(response[0]);
			activeNewPredictive = parseInt(response[0]);
			ReDrawActCalendar(type)
		} else {
			activeOrgCalendar = parseInt(response[0]);
			activeNewCalendar = parseInt(response[0]);
			ReDrawActCalendar(type);
		}

	}
});

// *****************************************************
// Widget for smartmow_calendar
// *****************************************************
$.widget("sv.smartmow_calendar", $.sv.widget, {

	initSelector : 'div[data-widget="indego.smartmow_calendar"]',
	options : {
		mode : '',
		id : ''
	},

	_create : function() {
		this._super();
		var id = this.options.id;
	},

	_update : function(response) {
		if (response.length === 0) {
			notify.error("Indego widget", "No predictive Calendar found ");
			return;
		}

		if (this.options.item == "indego.visu.exclusion_days") {
			colour = "#bebebe"
		} else {
			colour = "#0099000"
		}
		// Hier den Kalender zeichnen
		// DrawCalendar(TableName, CalNo, preFix)

		DrawCalendar("indego-pred-draw-calendar-9", 9, "S")
		FillDrawingCalendar([ response[0][0] ], "#bebebe", "S")
		FillDrawingCalendar([ response[0][1] ], "#099000", "S")

	}
});
// *****************************************************
// Widget for Symbols
// *****************************************************
$.widget("sv.symbol", $.sv.widget, {

	initSelector : '[data-widget="indego.symbol"]',

	options : {
		mode : '',
		val : '',
		id : ''
	},

	_create : function() {
		this._super()
	},
	_update : function(response) {
		// response will be an array, if more then one item is requested
		var bit = (this.options.mode == 'and');
		if (response instanceof Array) {
			for (var i = 0; i < response.length; i++) {
				if (this.options.mode == 'and') {
					bit = bit && (response[i] == this.options.val);
				} else {
					bit = bit || (response[i] == this.options.val);
				}
			}
		} else {
			bit = (response == this.options.val);
		}
		if (bit) {
			this.element.show();

		} else {
			this.element.hide();
		}
	}
});

// *****************************************************
// Widget for Params
// *****************************************************
$.widget("sv.params",
		$.sv.widget,
		{

			initSelector : '[data-widget="indego.params"]',

			options : {
				mode : '',
				val : '',
				id : ''
			},

			_create : function() {
				this._super()
			},
			_update : function(response) {
				myParam = response[0].split("|")[0]
				myValue = response[0].split("|")[1]
				switch (myParam) {
				case 'fire_uszu_popup':
					{
						if (myValue == 'True')
						{
							document.getElementById("indego-indego_uzsu").click()
						}
						break;
					}
				case 'svg_pos':
				{
					if (myValue != '')
						{
						actMowerPos = myValue 
						UpdateMowerPos(myValue);
						}
					break;
				}
				case 'wintermodus': {
					switch (myValue) {
					case 'False': {
						document.getElementById("wintermode_0").style.display = "block"
						document.getElementById("wintermode_1").style.display = "block"
						document.getElementById("wintermode_2").style.display = "block"
						document.getElementById("wintermode_3").style.display = "block"
						document.getElementById("wintermode_4").style.display = "block"
						document.getElementById("wintermode_5").style.display = "block"									
						break;
					}
					case 'True': {
						document.getElementById("wintermode_0").style.display = "none"
						document.getElementById("wintermode_1").style.display = "none"
						document.getElementById("wintermode_2").style.display = "none"
						document.getElementById("wintermode_3").style.display = "none"
						document.getElementById("wintermode_4").style.display = "none"
						document.getElementById("wintermode_5").style.display = "none"									
						break;
					}

					}
					break;
				}
				case 'cal2show': {
					switch (myValue) {
					case '1': {
						document.getElementById("show_sm_times").style.display = "none"
						document.getElementById("show_cal_times").style.display = "block"
						break;
					}
					case '2': {
						document.getElementById("show_sm_times").style.display = "block"
						document.getElementById("show_cal_times").style.display = "none"
						break;
					}
					default: {
						document.getElementById("show_sm_times").style.display = "none"
						document.getElementById("show_cal_times").style.display = "none"
					}
					}
					break;
				}
				case 'svg_mow_track':
					{
					  if (myValue != '')
						  {
						  	MowTrack = JSON.parse(myValue)
						  	DrawMowTrack(MowTrack)
						  }
					  else
						  {
						  	MowTrack = ''
						  	HideMowTrack()
						  }
					  break;
					}
				}

			}
		});

// *****************************************************
// Widget for Spinners
// *****************************************************
$
		.widget(
				"sv.spinner",
				$.sv.widget,
				{

					initSelector : '[data-widget="indego.spinner"]',

					options : {
						id : ''
					},

					_create : function() {
						this._super();
						this.options.id = this.element[0].id;

					},

					_update : function(response) {
						// get list of values
						var myVal = response.toString().trim();
						myObj = this.options.id.substring(7, 50)
						if (myVal == 0) {
							document.getElementById("overlay-" + myObj).className = "spinnerHidden"
						} else {
							document.getElementById("overlay-" + myObj).className = "overlayloader"
						}

					},

				});

// **********************************************************************
// Widget for Mower Type 0 = unknown 1 = 1000 Series 2=350/400er Series
// **********************************************************************
$
		.widget(
				"sv.status",
				$.sv.widget,
				{

					initSelector : '[data-widget="indego.status"]',

					options : {
						type : 0
					},

					_create : function() {
						this._super();
						this.id = 'MowerType';

					},

					_update : function(response) {
						try
						{ logo_small_ok = document.getElementById("logo_small_OK").value }
						catch (e)
						{}
						try
						{  logo_big_ok = document.getElementById("logo_big_OK").value }
						catch (e)
						{}

						if (response[0] == 1 && logo_big_ok == 1) {
							document.getElementById("Indego_big").style.display = "block"
							document.getElementById("Indego_small").style.display = "none"
							document.getElementById("Indego_small").style.display = "none"
						} else if (response[0] == 2 && logo_small_ok == 1) {
							try
							{
							document.getElementById("Indego_small").style.display = "block"
							document.getElementById("Indego_big").style.display = "none"
							document.getElementById("Indego_unknown").style.display = "none"
							}
							catch (e)
							{}
						} else {
							try
							{
							document.getElementById("Indego_unknown").style.display = "block"
							document.getElementById("Indego_small").style.display = "none"
							document.getElementById("Indego_big").style.display = "none"
							}
							catch (e)
							{}
						}
						// Additional Views for Indego 1000er Series
						if (response[0] == 1)
						{
							try
							{ document.getElementById("Advanced_Info1_4_1000_1").style.display = "block" }
							catch (e)
							{}
						}
						else
						{
							try
							{ document.getElementById("Advanced_Info1_4_1000_1").style.display = "none" }
							catch (e)
							{}
						}

					},

				});

// *****************************************************
// Widget for alerts
// *****************************************************
$
		.widget(
				"sv.alerts",
				$.sv.widget,
				{

					initSelector : '[data-widget="indego.alerts"]',

					options : {
						id : ''
					},

					_create : function() {
						this._super();
						this.options.id = this.element[0].id;

					},

					_update : function(response) {
						// get list of values
						var myVal = response[0];
						// Todo - sort correct

						var sorted = [];
						for ( var alert in myVal) {
							sorted[sorted.length] = alert;
						}
						sorted.sort();
						sorted.reverse();

						myHtml = '<table>'
						myHtml += '<h3>Meldungen</h3>'
						myHtml += '<hr>'

						for (counter in sorted) {
							var alert = sorted[counter]
							myDate = new Date(myVal[alert].date)
							myPrettyDate = myDate.toLocaleDateString('de-DE', {
								year : 'numeric',
								month : 'long',
								day : 'numeric',
								weekday : 'short',
								hour : 'numeric',
								minute : 'numeric'
							})

							myHtml += '<tr style="font-size:14px">'

							if (myVal[alert].read_status == 'unread') {
								myHtml += '<td colspan=3 align="left" style="color:red; font-size:14px; font-weight:700">'
										+ myPrettyDate
										+ ' - '
										+ myVal[alert].headline
										+ '</td><td></td><td></td>'
							} else {
								myHtml += '<td colspan=3 align="left"  style="font-size:14px; font-weight:400">'
										+ myPrettyDate
										+ ' - '
										+ myVal[alert].headline
										+ '</td><td></td><td></td>'
							}

							myHtml += '</tr>'
							myHtml += '<tr>'
							myHtml += '<td>'
							myHtml += '<label class="container"> <span> <input type="checkbox" align="center" class="inedgo_alert_check" id='
									+ alert + '> </span></label>'
							// "<label title='Mo'><input id = 'day_0' checked_0
							// type='checkbox' value='0'>Mo</label>" +
							myHtml += '</td>'
							myHtml += '<td>'

							myHtml += '</td>'
							if (myVal[alert].read_status == 'unread') {
								myHtml += '<td style="font-size:13px; font-weight:700">'
							} else {
								myHtml += '<td style="font-size:13px; font-weight:400">'
							}
							myHtml += myVal[alert].message + '<br>'
							myHtml += '<hr>'
							myHtml += '</td>'

							myHtml += '</tr>'

						}
						myHtml += '</table>'
						myHtml += '<table width="100%">'
						myHtml += '<tr>'
						myHtml += '<td width="120px"><button id="alert_delete" class="ui-btn ui-shadow ui-corner-all" onclick="MessageHandling(this.id)">Löschen</button></td>'
						myHtml += '<td width="120px"><button id="alert_read" class="ui-btn ui-shadow ui-corner-all" onclick="MessageHandling(this.id)">Gelesen</button></td>'
						myHtml += '</tr>'
						myHtml += '</table>'

						$('#indegoalertbox').html(myHtml)

					},

				});


//*****************************************************
//Widget for the garden-map
//*****************************************************
$.widget("sv.garden_map", $.sv.widget, {

	initSelector : '[data-widget="indego.garden_map"]',
	options : {id : ''},
	_create : function()
	{
		this._super();
	},
	_update : function(response)
	{
		document.getElementById("garden-image").innerHTML = response[0]
		orgMap = response[0]
		if (MowTrack != "")
			{
				DrawMowTrack(MowTrack)
			}
		if (actMowerPos != "")
			{
				UpdateMowerPos(actMowerPos)
			}
	}
});

//*****************************************************
//Widget for the weather-pictures
//*****************************************************
$.widget("sv.image", $.sv.widget, {

	initSelector : '[data-widget="indego.image"]',
	options : {id : ''},
	_create : function()
	{
		this._super();
	},
	_update : function(response)
	{
		this.bindings[0].src=response[0]
	}
});

//*****************************************************
//Widget for mode
//*****************************************************
$.widget("sv.mode", $.sv.widget, {

	initSelector : '[data-widget="indego.mode"]',
	options : {id : ''},
	_create : function()
	{
		this._super();
	},
	// 1 = Kalender, 2=Smart, 3 =AUS
	_update : function(response)
	{
		if (parseInt(response[0]) == 1)
			{
			  $("#SmartCollapse").children().collapsible("collapse");
			  $("#CalendarCollapse").children().collapsible("expand");
			}
		else if (parseInt(response[0]) == 2)
			{
			  $("#SmartCollapse").children().collapsible("expand");
			  $("#CalendarCollapse").children().collapsible("collapse");
			}
		else if (parseInt(response[0]) == 3)
			{
			  $("#SmartCollapse").children().collapsible("collapse");
			  $("#CalendarCollapse").children().collapsible("collapse");
			}
		
	}
});

///////////////////////////
//*****************************************************
//Jump to Anchor
//*****************************************************
$(document).on('click', 'a[href^="#jump"]', function(e) {
  // target element id
  var id = $(this).attr('href');
  // target element
  var $id = $(id);
  if ($id.length === 0) {
      return;
  }
  // prevent standard hash navigation (avoid blinking in IE)
  e.preventDefault();
  // top position relative to the document
  var pos = $id.offset().top-100;
  // animated top scrolling
  $('body, html').animate({scrollTop: pos});
});