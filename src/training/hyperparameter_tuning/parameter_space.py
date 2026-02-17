"""
Parameter space definition for hyperparameter tuning.

Defines:
- Parameter types and ranges
- Search space creation
- Parameter validation
"""

import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ParameterType(str, Enum):
    """Types of hyperparameters."""
    
    INT = "int"           # Integer parameter
    FLOAT = "float"       # Float parameter
    CATEGORICAL = "categorical"  # Categorical choices


@dataclass
class ParameterConfig:
    """Configuration for a single hyperparameter."""
    
    name: str
    param_type: ParameterType
    values: Union[List[Any], Tuple[float, float], Tuple[int, int]]
    default: Optional[Any] = None
    description: str = ""
    
    def __post_init__(self):
        """Validate parameter configuration."""
        if self.param_type == ParameterType.INT:
            if not isinstance(self.values, (tuple, list)):
                raise ValueError(f"INT parameter {self.name} requires tuple (min, max)")
            if len(self.values) != 2:
                raise ValueError(f"INT parameter {self.name} requires exactly 2 values")
            if not all(isinstance(v, int) for v in self.values):
                raise ValueError(f"INT parameter {self.name} values must be integers")
        
        elif self.param_type == ParameterType.FLOAT:
            if not isinstance(self.values, (tuple, list)):
                raise ValueError(f"FLOAT parameter {self.name} requires tuple (min, max)")
            if len(self.values) != 2:
                raise ValueError(f"FLOAT parameter {self.name} requires exactly 2 values")
            if not all(isinstance(v, (int, float)) for v in self.values):
                raise ValueError(f"FLOAT parameter {self.name} values must be numeric")
        
        elif self.param_type == ParameterType.CATEGORICAL:
            if not isinstance(self.values, (list, tuple)):
                raise ValueError(f"CATEGORICAL parameter {self.name} requires list of values")
            if not self.values:
                raise ValueError(f"CATEGORICAL parameter {self.name} cannot be empty")


class ParameterSpace:
    """
    Manages hyperparameter search space for a specific model.
    
    Defines which parameters to tune, their types, and valid ranges/values.
    """
    
    def __init__(self):
        """Initialize parameter space."""
        self._parameters: Dict[str, ParameterConfig] = {}
    
    def add_parameter(self, param: ParameterConfig) -> None:
        """
        Add a parameter to the search space.
        
        Args:
            param: ParameterConfig instance
        """
        self._parameters[param.name] = param
        logger.debug(f"Added parameter: {param.name} ({param.param_type})")
    
    def add_int_parameter(
        self,
        name: str,
        min_val: int,
        max_val: int,
        default: Optional[int] = None,
        description: str = ""
    ) -> None:
        """Add integer parameter."""
        param = ParameterConfig(
            name=name,
            param_type=ParameterType.INT,
            values=(min_val, max_val),
            default=default,
            description=description
        )
        self.add_parameter(param)
    
    def add_float_parameter(
        self,
        name: str,
        min_val: float,
        max_val: float,
        default: Optional[float] = None,
        description: str = ""
    ) -> None:
        """Add float parameter."""
        param = ParameterConfig(
            name=name,
            param_type=ParameterType.FLOAT,
            values=(min_val, max_val),
            default=default,
            description=description
        )
        self.add_parameter(param)
    
    def add_categorical_parameter(
        self,
        name: str,
        values: List[Any],
        default: Optional[Any] = None,
        description: str = ""
    ) -> None:
        """Add categorical parameter."""
        param = ParameterConfig(
            name=name,
            param_type=ParameterType.CATEGORICAL,
            values=values,
            default=default,
            description=description
        )
        self.add_parameter(param)
    
    def get_parameter(self, name: str) -> Optional[ParameterConfig]:
        """Get parameter by name."""
        return self._parameters.get(name)
    
    def get_all_parameters(self) -> Dict[str, ParameterConfig]:
        """Get all parameters."""
        return self._parameters.copy()
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate if configuration matches parameter space.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if valid, raises ValueError if invalid
        """
        for param_name, param_config in self._parameters.items():
            if param_name not in config:
                raise ValueError(f"Missing parameter: {param_name}")
            
            value = config[param_name]
            
            if param_config.param_type == ParameterType.INT:
                if not isinstance(value, int):
                    raise ValueError(f"{param_name} must be int, got {type(value)}")
                min_val, max_val = param_config.values
                if not (min_val <= value <= max_val):
                    raise ValueError(
                        f"{param_name} value {value} outside range [{min_val}, {max_val}]"
                    )
            
            elif param_config.param_type == ParameterType.FLOAT:
                if not isinstance(value, (int, float)):
                    raise ValueError(f"{param_name} must be float, got {type(value)}")
                min_val, max_val = param_config.values
                if not (min_val <= value <= max_val):
                    raise ValueError(
                        f"{param_name} value {value} outside range [{min_val}, {max_val}]"
                    )
            
            elif param_config.param_type == ParameterType.CATEGORICAL:
                if value not in param_config.values:
                    raise ValueError(
                        f"{param_name} value {value} not in {param_config.values}"
                    )
        
        return True


class SearchSpace:
    """Helper class for creating common search spaces."""
    
    @staticmethod
    def isolation_forest_space() -> ParameterSpace:
        """Create search space for Isolation Forest model."""
        space = ParameterSpace()
        
        space.add_int_parameter(
            "n_estimators",
            min_val=50,
            max_val=500,
            default=100,
            description="Number of base estimators"
        )
        
        space.add_float_parameter(
            "contamination",
            min_val=0.01,
            max_val=0.5,
            default=0.1,
            description="Expected proportion of outliers"
        )
        
        space.add_float_parameter(
            "max_samples_ratio",
            min_val=0.1,
            max_val=1.0,
            default=1.0,
            description="Ratio of samples used in each estimator"
        )
        
        space.add_int_parameter(
            "max_features",
            min_val=1,
            max_val=5,
            default=1,
            description="Number of features used in each estimator"
        )
        
        return space
    
    @staticmethod
    def one_class_svm_space() -> ParameterSpace:
        """Create search space for One-Class SVM model."""
        space = ParameterSpace()
        
        space.add_float_parameter(
            "nu",
            min_val=0.01,
            max_val=0.5,
            default=0.05,
            description="Upper bound on false positives"
        )
        
        space.add_categorical_parameter(
            "kernel",
            values=["linear", "poly", "rbf", "sigmoid"],
            default="rbf",
            description="Kernel type"
        )
        
        space.add_float_parameter(
            "gamma",
            min_val=0.001,
            max_val=1.0,
            default=0.1,
            description="Kernel coefficient"
        )
        
        space.add_int_parameter(
            "degree",
            min_val=2,
            max_val=5,
            default=3,
            description="Degree for poly kernel"
        )
        
        return space
    
    @staticmethod
    def local_outlier_factor_space() -> ParameterSpace:
        """Create search space for Local Outlier Factor model."""
        space = ParameterSpace()
        
        space.add_int_parameter(
            "n_neighbors",
            min_val=5,
            max_val=100,
            default=20,
            description="Number of neighbors"
        )
        
        space.add_categorical_parameter(
            "metric",
            values=["minkowski", "euclidean", "manhattan"],
            default="minkowski",
            description="Distance metric"
        )
        
        space.add_int_parameter(
            "p",
            min_val=1,
            max_val=3,
            default=2,
            description="Power for minkowski metric"
        )
        
        return space
