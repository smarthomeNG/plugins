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

//  var triggerid = trigger_block.getFieldValue('NAME');
  var triggerid = block.getFieldValue('NAME');
  var itemcode = Blockly.Python.valueToCode(block, 'TRIG_ITEM', Blockly.Python.ORDER_ATOMIC);
  var itemid = itemcode.split('"')[1] 

  var code = '';
  var trigger = '';
  var logicname = block.getFieldValue('LOGIC_NAME').toLowerCase().replace(" ", "_");
  block.setFieldValue(logicname, 'LOGIC_NAME');

  if (trigger_block.length > 0) {
    if (trigger_block[0].data == 'sh_trigger_cycle') {
      var trigger = 'cycle: ' + trigger_block[0].getFieldValue('TRIG_CYCLE');
    };
    if (trigger_block[0].data == 'sh_trigger_item') {
      var itemcode = Blockly.Python.valueToCode(trigger_block[0], 'TRIG_ITEM', Blockly.Python.ORDER_ATOMIC);
      var itemid = itemcode.split('"')[1] 
      var trigger = 'watchitem: ' + itemid;
    };
    if (trigger_block[0].data == 'sh_trigger_sun') {
      var offset    = trigger_block[0].getFieldValue('OFFSET');
      var plusminus = trigger_block[0].getFieldValue('PLUSMINUS');
      var sun       = trigger_block[0].getFieldValue('SUN');
      var checkbox_active = (trigger_block[0].getFieldValue('ACTIVE') == 'TRUE') ? 'True' : 'False';
      //var branch = Blockly.Python.statementToCode(block, 'DO') || '  pass\n';
      var trigger = 'crontab: ' + sun + plusminus + offset;
    };
    if (trigger_block[0].data == 'sh_trigger_daily') {
      var hh = trigger_block[0].getFieldValue('HH');
      var mm = trigger_block[0].getFieldValue('MM');
//      var checkbox_active = (block.getFieldValue('ACTIVE') == 'TRUE') ? 'True' : 'False';
//      var code = '#?#' + id + ':crontab = ' + mm + ' ' + hh + ' * * = ' + id + '\n';
      var trigger = 'crontab: ' + + mm + ' ' + hh + ' * *';
    };
    if (trigger != '') {
      code += '#yaml#'+logicname+':#filename: '+logicname+'.py#' + trigger + '\n';
    };
  };

  code += '"""\n' + 'Logic '+ logicname + '.py\n';
  code += '\n' + text_comment + '\n';
  
  if (trigger != '') {
    var trigger_comment = trigger_block[0].getFieldValue('COMMENT');
    code += '\nto be configured in /etc/logic.yaml:\n';
    code += "\n  "+logicname+":\n";
    if (trigger_comment != 'Kommentar') {
      code += "      # " + trigger_comment + "\n";
    };
    code += "      filename: "+logicname+".py\n";
    code += "      "+trigger+"\n";
  };

  code += '"""\n';
  code += "if (True):\n";
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
        .setAlign(Blockly.ALIGN_CENTRE)
        .appendField("Trigger: Auslösen bei Änderung von");
//    this.appendStatementInput('DO')
//        .appendField('starte');
    this.appendDummyInput()
        .appendField(new Blockly.FieldCheckbox("TRUE"), "ACTIVE")
        .appendField(new Blockly.FieldTextInput("Kommentar"), "COMMENT");
    this.appendDummyInput()
        .appendField("als Logik")
        .appendField(new Blockly.FieldTextInput("trigger_id"), "NAME")
        .appendField("speichern");
        
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Block wird ausgeführt, sobald sich der Wert des Triggers ändert.');
    }
};


/**
 * https://blockly-demo.appspot.com/static/demos/blockfactory/index.html#prgbjr
 */
// Blockly.Blocks['shtools_logger'] = {
//   init: function() {
//     this.setHelpUrl('http://www.example.com/');
//     this.setColour(45);
//     this.appendDummyInput()
//         .appendField("schreibe ins Log");
//     this.appendValueInput("LOGTEXT")
//         .setCheck("String");
//     this.appendDummyInput()
//         .appendField("mit log-level")
//         .appendField(new Blockly.FieldDropdown([["debug", "DEBUG"], ["info", "INFO"], ["warning", "WARNING"], ["error", "ERROR"], ["critical", "CRITICAL"]]), "LOGLEVEL");
//     this.setInputsInline(true);
//     this.setPreviousStatement(true);
//     this.setNextStatement(true);
//     this.setTooltip('');
//   }
// };
// Blockly.Python['shtools_logger'] = function(block) {
//   var loglevel = block.getFieldValue('LOGLEVEL').toLowerCase();
//   var logtext =  Blockly.Python.valueToCode(block, 'LOGTEXT', Blockly.Python.ORDER_NONE) || '\'\'';
//   var code = "logger." + loglevel + "(" + logtext + ")\n";
//   return code;
// };

Blockly.Python['sh_trigger_item'] = function(block)
{
  var triggerid = Blockly.Python.variableDB_.getDistinctName('trigger_id', Blockly.Variables.NAME_TYPE);
  var itemcode = Blockly.Python.valueToCode(block, 'TRIG_ITEM', Blockly.Python.ORDER_ATOMIC);
  var itemid = itemcode.split('"')[1] 
  //var item = block.getFieldValue('TRIG_ITEM');
  var branch = Blockly.Python.statementToCode(block, 'DO') ;
  //var branch = Blockly.Python.statementToCode(block, 'DO') || '  pass\n';
  var checkbox_active = (block.getFieldValue('ACTIVE') == 'TRUE') ? 'True' : 'False';
  var text_comment = block.getFieldValue('COMMENT');
  var code = '#?#' + triggerid + ':watchitem = ' + itemid + '\n';
//  code += '"""\n' + text_comment + '\n"""\n';
//  code += "if (logic.name == 'blockly_runner_" + triggerid + "') and " + checkbox_active + ":\n";
  //code += "  logger.info('ITEM TRIGGER id: \{\}, value: \{\}'.format(logic.name, trigger['value'] )) \n";
//  code += branch;
  var logtext =  Blockly.Python.valueToCode(block, 'TRIG_ITEM', Blockly.Python.ORDER_NONE) || '\'\'';
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
        .appendField('Sekunden auslösen');
//    this.appendStatementInput('DO')
//        .appendField('starte');
    this.appendDummyInput()
        .appendField(new Blockly.FieldCheckbox("TRUE"), "ACTIVE")
        .appendField(new Blockly.FieldTextInput("Kommentar"), "COMMENT");
    this.appendDummyInput()
        .appendField("als Logik")
        .appendField(new Blockly.FieldTextInput("trigger_id"), "NAME")
        .appendField("speichern");
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Block wird nach vorgegebener Zeit wiederholt ausgeführt.');
    }
};

Blockly.Python['sh_trigger_cycle'] = function(block) {
  var id = Blockly.Python.variableDB_.getDistinctName(block.getFieldValue('NAME'), Blockly.Variables.NAME_TYPE);
  var cycle = block.getFieldValue('TRIG_CYCLE');
  //var branch = Blockly.Python.statementToCode(block, 'DO') ;
  var branch = Blockly.Python.statementToCode(block, 'DO') || Blockly.Python.PASS;;
  var checkbox_active = (block.getFieldValue('ACTIVE') == 'TRUE') ? 'True' : 'False';
  var text_comment = block.getFieldValue('COMMENT');
  var code = '#?#' + id + ':cycle = ' + cycle + '\n';
//  code += '"""\n' + text_comment + '\n"""\n';
//  code += "if (logic.name == 'blockly_runner_" + id + "') and " + checkbox_active + ":\n";
  //code += "  logger.info('CYCLE TRIGGER by: \{\}, value: \{\}'.format(logic.name, trigger['value'] )) \n";
//  code += branch;
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
        .appendField(new Blockly.FieldTextInput('0', Blockly.FieldTextInput.nonnegativeIntegerValidator), 'OFFSET')
        .appendField('Minuten')
        .appendField(new Blockly.FieldDropdown( [['vor', '-'], ['nach', '+']] ), 'PLUSMINUS')
        .appendField('Sonnen-')
        .appendField(new Blockly.FieldDropdown( [['Aufgang', 'sunrise'], ['Untergang', 'sunset']] ), 'SUN');
    this.appendDummyInput()
        .appendField(new Blockly.FieldCheckbox("TRUE"), "ACTIVE")
        .appendField(new Blockly.FieldTextInput("Kommentar"), "COMMENT");
    this.appendDummyInput()
        .appendField("als Logik")
        .appendField(new Blockly.FieldTextInput("trigger_id"), "NAME")
        .appendField("speichern");
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Block wird vor/nach Sonnenaufgang/Sonnenuntergang ausgeführt.');
    }
};

Blockly.Python['sh_trigger_sun'] = function(block)
{
  var id = Blockly.Python.variableDB_.getDistinctName(
			'trigger_id', Blockly.Variables.NAME_TYPE);
  var offset    = block.getFieldValue('OFFSET');
  var plusminus = block.getFieldValue('PLUSMINUS');
  var sun       = block.getFieldValue('SUN');
  var branch = Blockly.Python.statementToCode(block, 'DO')  || '  pass\n';
  var checkbox_active = (block.getFieldValue('ACTIVE') == 'TRUE') ? 'True' : 'False';
  var text_comment = block.getFieldValue('COMMENT');
  //var branch = Blockly.Python.statementToCode(block, 'DO') || '  pass\n';
  var code = '#?#' + id + ':crontab = ' + sun + plusminus + offset + ' = ' + id + '\n';
//  code += "if (logic.name == 'blockly_runner_" + id + "') and " + checkbox_active + ":\n";
  //code += "  logger.info('SUN TRIGGER by: \{\}, value: \{\}'.format(logic.name, trigger['value'] )) \n";
//  code += branch;
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
        .appendField(new Blockly.FieldTextInput('0', Blockly.FieldTextInput.nonnegativeIntegerValidator), 'HH')
        .appendField(':')
        .appendField(new Blockly.FieldTextInput('0', Blockly.FieldTextInput.nonnegativeIntegerValidator), 'MM')
        .appendField('Uhr');
    this.appendDummyInput()
        .appendField(new Blockly.FieldCheckbox("TRUE"), "ACTIVE")
        .appendField(new Blockly.FieldTextInput("Kommentar"), "COMMENT");
    this.appendDummyInput()
        .appendField("als Logik")
        .appendField(new Blockly.FieldTextInput("trigger_id"), "NAME")
        .appendField("speichern");
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setTooltip('Block wird täglich zur gegebenen Stunde ausgeführt.');
    }
};

Blockly.Python['sh_trigger_daily'] = function(block)
{
  var id = Blockly.Python.variableDB_.getDistinctName(
			'trigger_id', Blockly.Variables.NAME_TYPE);
  var hh = block.getFieldValue('HH');
  var mm = block.getFieldValue('MM');
  //var branch = Blockly.Python.statementToCode(block, 'DO') ;
  var branch = Blockly.Python.statementToCode(block, 'DO') || '  pass\n';
  var checkbox_active = (block.getFieldValue('ACTIVE') == 'TRUE') ? 'True' : 'False';
  var text_comment = block.getFieldValue('COMMENT');
  var code = '#?#' + id + ':crontab = ' + mm + ' ' + hh + ' * * = ' + id + '\n';
//  code += '"""\n' + text_comment + '\n"""\n';
//  code += "if (logic.name == 'blockly_runner_" + id + "') and " + checkbox_active + ":\n";
  //code += "  logger.info('CRONTAB TRIGGER by: \{\}, value: \{\}'.format(logic.name, trigger['value'] )) \n";
//  code += branch;
  return code;
};
