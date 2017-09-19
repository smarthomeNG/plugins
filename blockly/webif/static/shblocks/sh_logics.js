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
  var trigger = '';
  var trigger_comment = trigger_block.getFieldValue('COMMENT');
  if (trigger_comment != 'Kommentar') {
    trigger += trigger_comment;
  };    
  return trigger;
}

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
    trigger += '    watchitem: ' + itemid;
  };
  if (trigger_block.data == 'sh_trigger_sun') {
    var offset    = trigger_block.getFieldValue('OFFSET');
    var plusminus = trigger_block.getFieldValue('PLUSMINUS');
    var sun       = trigger_block.getFieldValue('SUN');
    var checkbox_active = (trigger_block.getFieldValue('ACTIVE') == 'TRUE') ? 'True' : 'False';
    //var branch = Blockly.Python.statementToCode(block, 'DO') || '  pass\n';
    trigger += '    crontab: ' + sun + plusminus + offset;
  };
  if (trigger_block.data == 'sh_trigger_daily') {
//    var trigger_id= trigger_block.getFieldValue('NAME');
    var hh = trigger_block.getFieldValue('HH');
    var mm = trigger_block.getFieldValue('MM');
//    var checkbox_active = (block.getFieldValue('ACTIVE') == 'TRUE') ? 'True' : 'False';
//    var code = '#?#' + id + ':crontab = ' + mm + ' ' + hh + ' * * = ' + id + '\n';
    trigger += '    crontab: ' + + mm + ' ' + hh + ' * *';
  };
  if (trigger_id != '' && trigger_id != 'trigger_id')
  {
    trigger += ' = ' + trigger_id
  };
  return trigger;
}

function NextLevel(trigger_block, logicname)
{
  var tr_insert = ''
  var tr_comment = ''
  if (trigger_block != null) {
    if (trigger_block.data != null) {
//      tr_insert += "#trigger_block = '" + trigger_block.data + "'\n" ;
      var comment = GetTriggerComment(trigger_block)
      var trigger = GetTrigger(trigger_block);
      if (trigger.trim() != '') {
        tr_insert += '#yaml#'+logicname+':#filename: '+logicname+'.py#' + trigger.trim() + '#' + comment + '\n';
      };
      if (comment.trim() != '') {
        tr_comment += "    # " + comment + '\n';
      };
      tr_comment += trigger + '\n';
      
      var next_block = trigger_block.getNextBlock();
      var next = NextLevel(next_block, logicname);
      tr_insert += next[0];
      tr_comment += next[1];
    };
    return [tr_insert, tr_comment];
  };
}

Blockly.Python['sh_logic_main'] = function(block)
{
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


  if (trigger_block.length > 0) {
    var next = NextLevel(trigger_block[0], logicname);
    code += next[0];
  };

  code += '"""\n' + 'Logic '+ logicname + '.py\n';
  code += '\n' + text_comment + '\n';
  
  code += "\nTHIS FILE WAS GENERATED FROM A BLOCKY LOGIC WORKSHEET - DON'T EDIT THIS FILE, use the Blockly plugin instead !\n" 
  if (next[1] != '') {
    var trigger_comment = trigger_block[0].getFieldValue('COMMENT');
    code += '\nto be configured in /etc/logic.yaml:\n';
    code += "\n"+logicname+":\n";
    code += "    filename: "+logicname+".py\n";
    code += next[1];
  };
  code += '"""\n';

  var active = block.getFieldValue('ACTIVE');
  if (active == 'TRUE') {
    active = 'True';
  } else {
    active = 'False';
  };
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
        .appendField(new Blockly.FieldTextInput("Kommentar"), "COMMENT");
        
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
    this.data = 'sh_trigger_cycle'
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
        .appendField(new Blockly.FieldTextInput("Kommentar"), "COMMENT");
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
    this.data = 'sh_trigger_sun'
    this.setColour(190);
    this.appendDummyInput()
        .appendField('Trigger: Auslösen')
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
        .appendField(new Blockly.FieldTextInput("Kommentar"), "COMMENT");
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
    this.data = 'sh_trigger_daily'
    this.setColour(190);
    this.appendDummyInput()
        .appendField('Jeden Tag ')
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
        .appendField(new Blockly.FieldTextInput("Kommentar"), "COMMENT");
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
