// tslint:disable-next-line:export-just-namespace
export = fontawesome;
export as namespace fontawesome;
import * as commonTypes from '@fortawesome/fontawesome-common-types';
declare namespace fontawesome {
  type IconDefinition = commonTypes.IconDefinition;
  type IconLookup = commonTypes.IconLookup;
  type IconName = commonTypes.IconName;
  type IconPrefix = commonTypes.IconPrefix;
  const dom: DOM;
  const library: Library;
  const parse: { transform(transformString: string): Transform };
  const config: Config;
  function noAuto():void;
  function findIconDefinition(iconLookup: IconLookup): IconDefinition;
  function text(content: string, params?: Params): Text;
  function layer(
    assembler: (
      addLayerCallback: (layerToAdd: IconLookup | IconLookup[]) => void
    ) => void
  ): Layer;
  function icon(icon: IconName | IconLookup, params?: IconParams): Icon;

  type IconProp = IconName | [IconPrefix, IconName] | IconLookup;
  type FlipProp = "horizontal" | "vertical" | "both";
  type SizeProp =
    | "xs"
    | "lg"
    | "sm"
    | "1x"
    | "2x"
    | "3x"
    | "4x"
    | "5x"
    | "6x"
    | "7x"
    | "8x"
    | "9x"
    | "10x";
  type PullProp = "left" | "right";
  type RotateProp = 90 | 180 | 270;
  type FaSymbol = string | boolean;
  interface Config {
    familyPrefix: IconPrefix;
    replacementClass: string;
    autoReplaceSvg: true;
    autoAddCss: true;
    autoA11y: true;
    searchPseudoElements: false;
    observeMutations: true;
    keepOriginalSource: true;
    measurePerformance: false;
    showMissingIcons: true;
  }
  interface FontawesomeObject {
    readonly abstract: object;
    readonly html: string;
    readonly node: HTMLCollection;
  }
  interface Icon extends FontawesomeObject, IconDefinition {
    readonly type: "icon";
  }
  interface Text extends FontawesomeObject {
    readonly type: "text";
  }
  interface Layer extends FontawesomeObject {
    readonly type: "layer";
  }
  interface Attributes {
    [key: string]: number | string;
  }
  interface Styles {
    [key: string]: string;
  }
  interface Transform {
    size?: number;
    x?: number;
    y?: number;
    rotate?: number;
    flipX?: boolean;
    flipY?: boolean;
  }
  interface Params {
    transform?: Transform;
    title?: string;
    classes?: string | string[];
    attributes?: Attributes;
    styles?: Styles;
  }
  interface IconParams extends Params {
    symbol?: FaSymbol;
    mask?: IconLookup;
  }
  interface DOM {
    i2svg(params: { node: Node; callback: () => void }): void;
    css(): string;
    insertCss(): string;
  }
  interface Library {
    add(...definitions: IconDefinition[]): void;
    reset(): void;
  }
}
