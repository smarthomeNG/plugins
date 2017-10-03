/**
 * @license
 * Visual Blocks Editor
 *
 * Copyright 2012 Google Inc.
 * https://developers.google.com/blockly/
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * @fileoverview Logic blocks for Blockly.
 * @author q.neutron@gmail.com (Quynh Neutron)
 */
'use strict';

goog.provide('Blockly.Blocks.sh_trigger');

goog.require('Blockly.Blocks');


/**
 * Logic main block
 */
Blockly.Blocks['sh_logic_main'] = {
  /**
   * Block for if/elseif/else condition.
   * @this Blockly.Block
   */
  init: function() {
/**
    Blockly.HSV_SATURATION = 0.45; 
    Blockly.HSV_VALUE = 0.65;
 */
    this.setColour(125);
    this.appendValueInput("LOGIC")
        .setCheck("shItemType")
        .setAlign(Blockly.ALIGN_LEFT)
        .appendField("Logik")
        .appendField(new Blockly.FieldTextInput("new_logic"), 'LOGIC_NAME')
        .appendField('(Dateiname zum speichern ohne Extension)');
    this.appendStatementInput('DO');
//    this.appendStatementInput('DO')
//        .appendField('starte');
    this.appendDummyInput()
        .appendField(new Blockly.FieldCheckbox("TRUE"), "ACTIVE")
        .appendField(new Blockly.FieldTextInput("Kommentar"), "COMMENT");
        
    this.setPreviousStatement(false);
    this.setNextStatement(false);
    this.setTooltip('Block wird ausgeführt, sobald sich der Wert des Triggers ändert.');
    }
};


function GetTriggerComment(trigger_block)
{
  var comment = '';
  var trigger_comment = trigger_block.getFieldValue('COMMENT');
  if (trigger_comment != 'Kommentar') {
    comment += trigger_comment;
  };    
  return comment.trim();
};

function GetTrigger(trigger_block)
{
  var trigger = '';
  var trigger_id = trigger_block.getFieldValue('NAME');
  if (trigger_block.data == 'sh_trigger_cycle') {
    var trigger_id= trigger_block.getFieldValue('NAME');
    trigger += '    cycle: ' + trigger_block.getFieldValue('TRIG_CYCLE');
  };
  if (trigger_block.data == 'sh_trigger_item') {
    var trigger_id= trigger_block.getFieldValue('NAME');
    var itemcode = Blockly.Python.valueToCode(trigger_block, 'TRIG_ITEM', Blockly.Python.ORDER_ATOMIC);
    var itemid = itemcode.split('"')[1] 
    trigger += '    watch_item: ' + itemid;
  };
  if (trigger_block.data == 'sh_trigger_sun') {
    var offset    = trigger_block.getFieldValue('OFFSET');
    var plusminus = trigger_block.getFieldValue('PLUSMINUS');
    var sun       = trigger_block.getFieldValue('SUN');
    trigger += '    crontab: ' + sun + plusminus + offset;
  };
  if (trigger_block.data == 'sh_trigger_daily') {
//    var trigger_id= trigger_block.getFieldValue('NAME');
    var hh = trigger_block.getFieldValue('HH');
    var mm = trigger_block.getFieldValue('MM');
    trigger += '    crontab: ' + + mm + ' ' + hh + ' * *';
  };
  if (trigger_block.data == 'sh_trigger_init') {
    trigger += '    crontab: init';
  };
  if (trigger_id != '' && trigger_id != 'trigger_id')
  {
    trigger += ' = ' + trigger_id
  };
  return trigger;
};

function GetMultiTriggers(trigger_block)
{
  var cr_list = [];
  var crc_list = [];
  var wi_list = [];
  var wic_list = [];
  var contab_triggers = ['sh_trigger_sun', 'sh_trigger_daily', 'sh_trigger_init'];
  var next_block = trigger_block;
  
  while (next_block != null) {
    if (next_block.data != '')
    {
      if (contab_triggers.indexOf(next_block.data) > -1)
      {
        var trigger = GetTrigger(next_block);
        if (trigger.trim() != '') {
          cr_list.push(trigger.split(':')[1].trim());
        };
        crc_list.push(GetTriggerComment(next_block));
      };
      if (next_block.data == 'sh_trigger_item')
      {
        var trigger = GetTrigger(next_block);
        if (trigger.trim() != '') {
          wi_list.push(trigger.split(':')[1].trim());
        };
        wic_list.push(GetTriggerComment(next_block));
      };
    };
    var next_block = next_block.getNextBlock();
  };
  return [cr_list, crc_list, wi_list, wic_list];
};

function NextLevel(trigger_block, logicname, ignore_crontab, ignore_watchitem)
{
  var tr_insert = ''
  var tr_comment = ''
  if (trigger_block != null) {
    if (trigger_block.data != null) {
      var comment = GetTriggerComment(trigger_block)
      var trigger = GetTrigger(trigger_block);
      if (ignore_crontab && (trigger.trim().substring(0,8) == 'crontab:'))
      {
        trigger = '';
      };
      if (ignore_watchitem && (trigger.trim().substring(0,11) == 'watch_item:'))
      {
        trigger = '';
      };
      if (trigger.trim() != '') {
        tr_insert += '#trigger#'+logicname+'#filename: '+logicname+'.py#' + trigger.trim() + '#' + comment + '\n';
        var line = trigger;
        if (comment != '') {
          line = line.padEnd(50) + ' # ' + comment
        };
        tr_comment += line + '\n';
      };
      
      var next_block = trigger_block.getNextBlock();
      var next = NextLevel(next_block, logicname, ignore_crontab, ignore_watchitem);
      tr_insert += next[0];
      tr_comment += next[1];
    };
    return [tr_insert, tr_comment];
  };
};

Blockly.Python['sh_logic_main'] = function(block)
{
  this.data = 'sh_logic_main'
  var trigger_block = block.getChildren();
  var triggerid = Blockly.Python.variableDB_.getDistinctName('trigger_id', Blockly.Variables.NAME_TYPE);
  var itemcode = Blockly.Python.valueToCode(block, 'TRIG_ITEM', Blockly.Python.ORDER_ATOMIC);
  var itemid = itemcode.split('"')[1] 
  //var item = block.getFieldValue('TRIG_ITEM');
  var branch = Blockly.Python.statementToCode(block, 'DO') ;
  //var branch = Blockly.Python.statementToCode(block, 'DO') || '  pass\n';
  var checkbox_active = (block.getFieldValue('ACTIVE') == 'TRUE') ? 'True' : 'False';
  var text_comment = block.getFieldValue('COMMENT');

  var triggerid = block.getFieldValue('NAME');
  var itemcode = Blockly.Python.valueToCode(block, 'TRIG_ITEM', Blockly.Python.ORDER_ATOMIC);
  var itemid = itemcode.split('"')[1] 

  var code = '';
  var trigger = '';
  var logicname = block.getFieldValue('LOGIC_NAME').toLowerCase().replace(" ", "_");
  block.setFieldValue(logicname, 'LOGIC_NAME');

  var active = block.getFieldValue('ACTIVE');
  if (active == 'TRUE') {
    active = 'True';
  } else {
    active = 'False';
  };

  if (text_comment.length > 0) {
    code += '#comment#'+logicname+'#filename: '+logicname+'.py#active: ' + active + '#' + text_comment + '\n';
  };

  var tr_list = GetMultiTriggers(trigger_block[0]);
  var tr_crontab_list = tr_list[0];
  var tr_crontabc_list = tr_list[1];
  var tr_watchitem_list = tr_list[2];
  var tr_watchitemc_list = tr_list[3];

  if (trigger_block.length > 0) {
    var next = NextLevel(trigger_block[0], logicname, (tr_crontab_list.length > 1), (tr_watchitem_list.length > 1));
    code += next[0];
  };

  if (tr_crontab_list.length > 1)
  {
    var tr_list = '';
    var co_list = '';
    for (var t in tr_crontab_list) {
      if (t > 0) {
        tr_list += ',';
        co_list += ',';
      };
      tr_list += "'"+tr_crontab_list[t]+"'";
      co_list += "'"+tr_crontabc_list[t]+"'";
    };
    code += '#trigger#'+logicname+'#filename: '+logicname+'.py#crontab: [' + tr_list + ']#[' + co_list + ']\n';
  };
  
  if (tr_watchitem_list.length > 1)
  {
    var tr_list = '';
    var co_list = '';
    for (var t in tr_watchitem_list) {
      if (t > 0) {
        tr_list += ',';
        co_list += ',';
      };
      tr_list += "'"+tr_watchitem_list[t]+"'";
      co_list += "'"+tr_watchitemc_list[t]+"'";
    };
    code += '#trigger#'+logicname+'#filename: '+logicname+'.py#watch_item: [' + tr_list + ']#[' + co_list + ']\n';
  };
  
  code += '"""\n' + 'Logic '+ logicname + '.py\n';
  code += '\n' + text_comment + '\n';
  
  code += "\nTHIS FILE WAS GENERATED FROM A BLOCKY LOGIC WORKSHEET - DON'T EDIT THIS FILE, use the Blockly plugin instead !\n" 
  if (next[1] != '') {
    var trigger_comment = trigger_block[0].getFieldValue('COMMENT');
    code += '\nto be configured in /etc/logic.yaml:\n';
    code += "\n"+logicname+":\n";
    var line = "    filename: "+logicname+".py"
    if (text_comment != '') {
      line = line.padEnd(50) + ' # ' + text_comment
    };
    code += line + '\n';
    code += next[1];
  };
  
  if (tr_watchitem_list.length > 1)
  {
    code += '    watch_item:\n'
    for (var t in tr_watchitem_list) {
      code += '     - ' + tr_watchitem_list[t] + '\n';
    };
  };
  if (tr_crontab_list.length > 1)
  {
    code += '    crontab:\n'
    for (var t in tr_crontab_list) {
      code += '     - ' + tr_crontab_list[t] + '\n';
    };
  };
  code += '"""\n';

  code += "logic_active = "+ active +"\n";
  code += "if (logic_active == True):\n";
  //code += "  logger.info('ITEM TRIGGER id: \{\}, value: \{\}'.format(logic.name, trigger['value'] )) \n";
  code += branch;
  return code + "\n\n";
};


/**
 * Trigger die Logic bei Änderung des Items
 */
Blockly.Blocks['sh_trigger_item'] = {
  /**
   * Block for if/elseif/else condition.
   * @this Blockly.Block
   */
  init: function() {
    this.data = 'sh_trigger_item'
    this.setColour(190);
    this.appendValueInput("TRIG_ITEM")
        .setCheck("shItemType")
        .setAlign(Blockly.ALIGN_LEFT)
        .appendField("Trigger: Auslösen bei Änderung von");
//    this.appendStatementInput('DO')
//        .appendField('starte');
//    this.appendDummyInput()
//        .appendField(new Blockly.FieldCheckbox("TRUE"), "ACTIVE")
    this.appendDummyInput()
        .appendField("als Trigger")
        .appendField(new Blockly.FieldTextInput("trigger_id"), "NAME");
    this.appendDummyInput()
        .appendField("Kommentar")
        .appendField(new Blockly.FieldTextInput(""), "COMMENT");
        
    this.setInputsInline(false);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Block wird ausgeführt, sobald sich der Wert des Triggers ändert.');
    }
};

Blockly.Python['sh_trigger_item'] = function(block)
{
  var code = '';
  return code;
};


/**
 * Trigger ... alle x sec.
 */
Blockly.Blocks['sh_trigger_cycle'] = {
  /**
   * Block for
   * @this Blockly.Block
   */
  init: function() {
    this.data = 'sh_trigger_cycle';
    this.setColour(190);
    this.appendDummyInput()
        .appendField('Trigger: alle')
//        .appendField(new Blockly.FieldTextInput('60',
//            Blockly.FieldTextInput.nonnegativeIntegerValidator), 'TRIG_CYCLE')
        .appendField(new Blockly.FieldNumber(60, 0), 'TRIG_CYCLE')
        .appendField('Sekunden auslösen')
//    this.appendDummyInput()
        .appendField("als Trigger")
        .appendField(new Blockly.FieldTextInput("trigger_id"), "NAME");
    this.appendDummyInput()
        .appendField("Kommentar")
        .appendField(new Blockly.FieldTextInput(""), "COMMENT");
    this.setInputsInline(false);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Block wird nach vorgegebener Zeit wiederholt ausgeführt.');
    }
};

Blockly.Python['sh_trigger_cycle'] = function(block) {
  var code = ''
  return code;
};

/**
 * Trigger vor/nach Sonnen-Auf-/Untergang.
 */
Blockly.Blocks['sh_trigger_sun'] = {
  /**
   * Block for
   * @this Blockly.Block
   */
  init: function() {
    this.data = 'sh_trigger_sun';
    this.setColour(190);
    this.appendDummyInput()
        .appendField('Trigger (crontab): Auslösen')
//        .appendField(new Blockly.FieldTextInput('0', Blockly.FieldTextInput.nonnegativeIntegerValidator), 'OFFSET')
        .appendField(new Blockly.FieldNumber(0, 0), 'OFFSET')
        .appendField('Minuten')
        .appendField(new Blockly.FieldDropdown( [['vor', '-'], ['nach', '+']] ), 'PLUSMINUS')
        .appendField('Sonnen-')
        .appendField(new Blockly.FieldDropdown( [['Aufgang', 'sunrise'], ['Untergang', 'sunset']] ), 'SUN')
        .appendField("als Trigger")
        .appendField(new Blockly.FieldTextInput("trigger_id"), "NAME");
    this.appendDummyInput()
        .appendField("Kommentar")
        .appendField(new Blockly.FieldTextInput(""), "COMMENT");
    this.setInputsInline(false);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Block wird vor/nach Sonnenaufgang/Sonnenuntergang ausgeführt.');
    }
};

Blockly.Python['sh_trigger_sun'] = function(block)
{
  var code = '';
  return code;
};


/**
 * Trigger taeglich um HH:MM Uhr
 */
Blockly.Blocks['sh_trigger_daily'] = {
  /**
   * Block for
   * @this Blockly.Block
   */
  init: function() {
    this.data = 'sh_trigger_daily';
    this.setColour(190);
    this.appendDummyInput()
        .appendField('Trigger (crontab): Jeden Tag ')
        .appendField('um')
//        .appendField(new Blockly.FieldTextInput('0', Blockly.FieldTextInput.nonnegativeIntegerValidator), 'HH')
        .appendField(new Blockly.FieldNumber(0, 0), 'HH')
        .appendField(':')
//        .appendField(new Blockly.FieldTextInput('0', Blockly.FieldTextInput.nonnegativeIntegerValidator), 'MM')
        .appendField(new Blockly.FieldNumber(0, 0), 'MM')
        .appendField('Uhr')
//    this.appendDummyInput()
//        .appendField(new Blockly.FieldCheckbox("TRUE"), "ACTIVE");
        .appendField("als Trigger")
        .appendField(new Blockly.FieldTextInput("trigger_id"), "NAME");
    this.appendDummyInput()
        .appendField("Kommentar")
        .appendField(new Blockly.FieldTextInput(""), "COMMENT");
    this.setInputsInline(false);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Block wird täglich zur gegebenen Stunde ausgeführt.');
    }
};

Blockly.Python['sh_trigger_daily'] = function(block)
{
  var code = '';
  return code;
};


/**
 * Trigger bei Initialisierung auslösen
 */
Blockly.Blocks['sh_trigger_init'] = {
  /**
   * Block for
   * @this Blockly.Block
   */
  init: function() {
    this.data = 'sh_trigger_init';
    this.setColour(190);
    this.appendDummyInput()
        .appendField('Trigger (crontab): Bei Initialisierung auslosen, ')
        .appendField("als Trigger")
        .appendField(new Blockly.FieldTextInput("Init"), "NAME");
    this.appendDummyInput()
        .appendField("Kommentar")
        .appendField(new Blockly.FieldTextInput(""), "COMMENT");
    this.setInputsInline(false);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Block wird bei der Initialisierung ausgeführt.');
    }
};

Blockly.Python['sh_trigger_init'] = function(block)
{
  var code = '';
  return code;
};
