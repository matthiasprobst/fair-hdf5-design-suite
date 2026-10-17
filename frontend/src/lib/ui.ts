import type { LucideIcon } from 'lucide-react';
import { Activity, ArrowDownToLine, Box, Braces, Cable, CircleGauge, ClipboardList, Cog, Database, FileCode2, FileDigit, FileJson2, FileText, Folder, Gauge, GitBranch, HardDrive, Layers, LayoutTemplate, Network, Radio, RotateCcw, Ruler, ShieldCheck, SlidersHorizontal, Thermometer, Waves, Wind } from 'lucide-react';
export type IconComponent = LucideIcon;
export const ICONS:Record<string,IconComponent> = {
  fan:Wind,experiment_setup:Box,boundary_condition:SlidersHorizontal,pressure_sensor:Gauge,temperature_sensor:Thermometer,torque_sensor:RotateCcw,
  flow_sensor:Waves,vibration_sensor:Activity,custom_sensor:CircleGauge,daq:Radio,controller:SlidersHorizontal,power_supply:HardDrive,data_processor:Braces,process:Cog,data_processing:Cog,filter_process:SlidersHorizontal,unit_conversion:Ruler,custom_process:Cog,group:Folder,dataset:Database,metadata:FileText,
};
export const CATEGORY_ICONS:Record<string,IconComponent> = {
 Experiment:Box, Sensor:Activity, Equipment:HardDrive, Process:SlidersHorizontal,
 'HDF5 structure':Database, Metadata:FileJson2, Template:LayoutTemplate,
};
export const MORE_ICONS = {ArrowDownToLine,Braces,Cable,CircleGauge,ClipboardList,FileCode2,FileDigit,GitBranch,Layers,Network,Ruler,ShieldCheck};
export const TYPE_DESCRIPTIONS:Record<string,string> = {
 fan:'Industrial radial fan for flow characterization',experiment_setup:'Experimental test rig',boundary_condition:'Inlet or outlet condition',
 pressure_sensor:'Measures static pressure',temperature_sensor:'Measures air temperature',
 torque_sensor:'Measures shaft torque',flow_sensor:'Measures volumetric flow rate',vibration_sensor:'Measures vibration',custom_sensor:'Configurable measurement device',
 daq:'Multi-channel data acquisition system',controller:'Controls the experiment',power_supply:'Power supply or drive',data_processor:'Data analysis hardware',process:'Process and store research data',data_processing:'Processing pipeline',filter_process:'Filtering and averaging',unit_conversion:'Quantity conversion',custom_process:'Custom data processing',
 group:'Hierarchical HDF5 container',dataset:'Numerical measurement data',
 metadata:'Experimental conditions and provenance',
};
export const COLORS:Record<string,string> = {
 fan:'purple',experiment_setup:'purple',boundary_condition:'purple',pressure_sensor:'blue',temperature_sensor:'blue',torque_sensor:'blue',flow_sensor:'blue',vibration_sensor:'blue',custom_sensor:'blue',
 daq:'green',controller:'green',power_supply:'green',data_processor:'green',process:'orange',data_processing:'orange',filter_process:'orange',unit_conversion:'orange',custom_process:'orange',group:'coral',dataset:'coral',metadata:'violet',
};

export function nodeTone(type: string, color?: string): string {
  return color ? ({amber:'orange',rose:'coral'}[color] || color) : COLORS[type] || 'blue';
}
