"""
使用 Pydantic 定义静态建筑信息的严格数据模式 (V9.0 - 最终灵活健壮版)。
此版本通过引入通用的“键-值”存储字段(extra='allow')和为顶层模型添加
描述性文档字符串，彻底解决了两个核心问题：
1.  修复了 "Must provide description" 的运行时错误。
2.  极大地增强了模型的灵活性，使其能够捕获任何未预先定义的字段，
    从而完美适应不同数据源中多样化的信息，实现了结构化与灵活性的平衡。
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any

# ==============================================================================
# 1. 创建一个可扩展的基础模型
# ==============================================================================

class FlexibleModel(BaseModel):
    """
    一个可扩展的基础模型，允许捕获任何未预先定义的字段。
    所有其他模型都将继承自这个模型，以获得灵活性。
    A base model that allows extra fields to be captured.
    All other models will inherit from this to gain flexibility.
    """
    class Config:
        extra = 'allow' # 允许额外的字段
        populate_by_name = True

# ==============================================================================
# 2. 交互接口模型 (Interaction Interfaces)
# ==============================================================================

class ActionVariable(FlexibleModel):
    """描述一个可控制的变量。(Describes a controllable variable.)"""
    name: Optional[str] = None
    description: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: Optional[str] = None

class ActionSpaceInfo(FlexibleModel):
    """包含所有可控制变量的集合。(Contains the set of all controllable variables.)"""
    actions: Optional[List[ActionVariable]] = None

class ObservationVariable(FlexibleModel):
    """描述一个可观测的状态变量。(Describes an observable state variable.)"""
    name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None

class ObservationSpaceInfo(FlexibleModel):
    """包含所有可观测变量的集合。(Contains the set of all observable variables.)"""
    observations: Optional[List[ObservationVariable]] = None

# ==============================================================================
# 3. 建筑详细信息模型 (Detailed Building Info)
# ==============================================================================

class Layer(FlexibleModel):
    """描述围护结构中的一个材料层。(Describes a material layer in the envelope.)"""
    name: Optional[str] = None
    thickness_m: Optional[float] = None
    thermal_conductivity_W_mK: Optional[float] = None
    specific_heat_capacity_J_kgK: Optional[float] = None
    density_kg_m3: Optional[float] = None

class EnvelopeComponentWithLayers(FlexibleModel):
    """一个包含详细分层信息和其他热工参数的围护结构组件。(An envelope component with detailed layers and other thermal parameters.)"""
    layers: Optional[List[Layer]] = None
    ir_emissivity_outside: Optional[float] = None
    solar_emissivity_outside: Optional[float] = None
    ir_emissivity_inside: Optional[float] = None
    solar_emissivity_inside: Optional[float] = None

class WindowGroup(FlexibleModel):
    """描述一组窗户的信息。(Describes a group of windows.)"""
    name: Optional[str] = None
    area_m2: Optional[float] = None
    orientation: Optional[str] = None
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    type: Optional[str] = None
    glass_thickness_mm: Optional[float] = None
    air_gap_mm: Optional[float] = None

class EnvelopeInfo(FlexibleModel):
    """包含所有围护结构组件的详细热工信息。(Contains detailed thermal information for all envelope components.)"""
    exterior_walls: Optional[EnvelopeComponentWithLayers] = None
    roof: Optional[EnvelopeComponentWithLayers] = None
    floors: Optional[EnvelopeComponentWithLayers] = None
    windows: Optional[List[WindowGroup]] = None

class InternalGainSource(FlexibleModel):
    """用于描述内部热源的具体类型和描述。(Describes the specific type and description of an internal heat source.)"""
    type: Optional[str] = None
    description: Optional[str] = None

class InternalHeatGains(FlexibleModel):
    """结构化的内部热源。(Structured internal heat gains.)"""
    internal_gains: Optional[List[InternalGainSource]] = None
    plug_loads: Optional[Union[dict, str]] = None
    lighting: Optional[Union[dict, str]] = None
    occupied_period_max: Optional[float] = None
    unoccupied_period_max: Optional[float] = None

class TemperatureSetpoints(FlexibleModel):
    """结构化的温度设定点。(Structured temperature setpoints.)"""
    occupied: Optional[dict[str, int]] = None
    unoccupied: Optional[dict[str, int]] = None

class OccupancySchedule(FlexibleModel):
    """结构化的人员在室时间表。(Structured occupancy schedule.)"""
    max_occupancy: Optional[int] = None
    occupied_hours: Optional[Union[dict, List[dict]]] = None

class ZoneLoads(FlexibleModel):
    """描述一个区域的负荷信息。(Describes the load information for a zone.)"""
    name: Optional[str] = None
    occupancy_schedule: Optional[Union[OccupancySchedule, str]] = None
    internal_heat_gains: Optional[InternalHeatGains] = Field(None, alias='internal_gains')
    temperature_setpoints: Optional[TemperatureSetpoints] = None
    zone_floor_area: Optional[float] = None

class InternalLoadsInfo(FlexibleModel):
    """包含所有分区的内部负荷和运行模式信息。(Contains internal load and operational schedule information for all zones.)"""
    zones: Optional[List[ZoneLoads]] = None

class HVACComponentDetail(FlexibleModel):
    """描述LLM可能返回的详细HVAC组件。(Describes detailed HVAC components that the LLM might return.)"""
    name: Optional[str] = None
    nominal_mass_flow_rate_kg_s: Optional[float] = Field(None, alias='nominal_mass_flow_rate_kg_s')
    nominal_pressure_rise_kPa: Optional[float] = Field(None, alias='nominal_pressure_rise_kPa')
    total_efficiency: Optional[float] = None

class HVACSystem(FlexibleModel):
    """描述一个完整的HVAC系统。(Describes a complete HVAC system.)"""
    type: Optional[str] = None
    description: Optional[str] = None
    nominal_heating_capacity_kW: Optional[float] = None
    components: Optional[List[Union[HVACComponentDetail, str]]] = None
    fan: Optional[dict] = None
    chiller: Optional[dict] = None
    boiler: Optional[dict] = None
    controller: Optional[dict] = None

class HVACInfo(FlexibleModel):
    """包含建筑中所有HVAC系统的信息。(Contains information on all HVAC systems in the building.)"""
    hvac_systems: Optional[List[HVACSystem]] = None

class GeneralInfo(FlexibleModel):
    """建筑的总体概况信息。(General overview information of the building.)"""
    building_type: Optional[str] = None
    location: Optional[str] = None
    climate_zone: Optional[str] = None
    total_floor_area: Optional[float] = None
    number_of_floors: Optional[int] = None
    year_of_construction: Optional[int] = None

class BuildingInfo(FlexibleModel):
    """整合了所有详细信息的建筑主模型。(The main building model integrating all detailed information.)"""
    general: Optional[GeneralInfo] = None
    envelope: Optional[EnvelopeInfo] = None
    internal_loads: Optional[InternalLoadsInfo] = None
    hvac: Optional[HVACInfo] = None

# ==============================================================================
# 4. 顶层主模型 (Master Schema)
# ==============================================================================

class StaticBuildingData(FlexibleModel):
    """
    This is the main container for all static building information extracted from
    a technical document. It includes details about the building's interaction
    interfaces (actions and observations) and its physical properties.
    """
    action_space: Optional[ActionSpaceInfo] = None
    observation_space: Optional[ObservationSpaceInfo] = None
    building_info: Optional[BuildingInfo] = None