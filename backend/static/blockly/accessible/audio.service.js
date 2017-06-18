/**
 * AccessibleBlockly
 *
 * Copyright 2016 Google Inc.
 * https://developers.google.com/blockly/
 *
 * Licensed under the Apache License, Version 2.0 (the 'License');
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * @fileoverview Angular2 Service that plays audio files.
 * @author sll@google.com (Sean Lip)
 */

blocklyApp.AudioService = ng.core
  .Class({
    constructor: [function() {
      // We do not play any audio unless a media path prefix is specified.
      this.canPlayAudio = false;
      if (ACCESSIBLE_GLOBALS.hasOwnProperty('mediaPathPrefix')) {
        this.canPlayAudio = true;
        var mediaPathPrefix = ACCESSIBLE_GLOBALS['mediaPathPrefix'];
        this.AUDIO_PATHS_ = {
          'connect': mediaPathPrefix + 'click.mp3',
          'delete': mediaPathPrefix + 'delete.mp3'
        };
      }

      // TODO(sll): Add ogg and mp3 fallbacks.
      this.cachedAudioFiles_ = {};
    }],
    play_: function(audioId) {
      if (this.canPlayAudio) {
        if (!this.cachedAudioFiles_.hasOwnProperty(audioId)) {
          this.cachedAudioFiles_[audioId] = new Audio(
              this.AUDIO_PATHS_[audioId]);
        }
        this.cachedAudioFiles_[audioId].play();
      }
    },
    playConnectSound: function() {
      this.play_('connect');
    },
    playDeleteSound: function() {
      this.play_('delete');
    }
  });
