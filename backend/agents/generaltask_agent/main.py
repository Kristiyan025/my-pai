"""
General Task Agent - Handles miscellaneous computational tasks.

Includes:
- Math calculations
- Code execution (Python sandbox)
- Data analysis helpers
- Utility functions
"""

import os
import sys
import json
from typing import Optional, Any, Dict, List
from datetime import datetime
import math
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="General Task Agent",
    description="General-purpose task execution agent",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Request/Response Models ==============

class MathExpressionRequest(BaseModel):
    expression: str


class MathResult(BaseModel):
    expression: str
    result: Any
    steps: Optional[List[str]] = None


class CodeExecutionRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 30


class CodeExecutionResult(BaseModel):
    output: str
    error: Optional[str] = None
    execution_time_ms: float


class DataAnalysisRequest(BaseModel):
    data: List[Any]
    operation: str  # mean, median, sum, std, min, max, count, describe


class DateTimeRequest(BaseModel):
    operation: str  # now, format, diff, add
    value: Optional[str] = None
    format: Optional[str] = None
    unit: Optional[str] = None
    amount: Optional[int] = None


class UnitConversionRequest(BaseModel):
    value: float
    from_unit: str
    to_unit: str


# ============== Safe Math Evaluation ==============

SAFE_MATH_FUNCS = {
    'abs': abs,
    'round': round,
    'min': min,
    'max': max,
    'sum': sum,
    'len': len,
    'pow': pow,
    'sqrt': math.sqrt,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'log': math.log,
    'log10': math.log10,
    'log2': math.log2,
    'exp': math.exp,
    'floor': math.floor,
    'ceil': math.ceil,
    'factorial': math.factorial,
    'gcd': math.gcd,
    'pi': math.pi,
    'e': math.e,
}


def safe_eval_math(expression: str) -> Any:
    """
    Safely evaluate a mathematical expression.
    
    Only allows:
    - Numbers (int, float)
    - Basic operators (+, -, *, /, **, %, //)
    - Parentheses
    - Allowed math functions
    """
    # Remove whitespace
    expression = expression.strip()
    
    # Check for dangerous patterns
    dangerous_patterns = [
        '__', 'import', 'exec', 'eval', 'open', 'file', 
        'input', 'print', 'os.', 'sys.', 'subprocess'
    ]
    for pattern in dangerous_patterns:
        if pattern in expression.lower():
            raise ValueError(f"Expression contains forbidden pattern: {pattern}")
    
    try:
        # First try simple numeric evaluation
        result = eval(expression, {"__builtins__": {}}, SAFE_MATH_FUNCS)
        return result
    except Exception as e:
        raise ValueError(f"Invalid expression: {str(e)}")


# ============== Safe Code Execution ==============

def execute_python_safe(code: str, timeout: int = 30) -> tuple:
    """
    Execute Python code in a restricted environment.
    
    Returns (output, error, execution_time_ms)
    """
    import io
    import contextlib
    import time
    import signal
    
    # Restricted builtins
    safe_builtins = {
        'abs': abs, 'all': all, 'any': any, 'bin': bin,
        'bool': bool, 'bytearray': bytearray, 'bytes': bytes,
        'chr': chr, 'dict': dict, 'divmod': divmod,
        'enumerate': enumerate, 'filter': filter, 'float': float,
        'format': format, 'frozenset': frozenset, 'hash': hash,
        'hex': hex, 'int': int, 'isinstance': isinstance,
        'issubclass': issubclass, 'iter': iter, 'len': len,
        'list': list, 'map': map, 'max': max, 'min': min,
        'oct': oct, 'ord': ord, 'pow': pow, 'print': print,
        'range': range, 'repr': repr, 'reversed': reversed,
        'round': round, 'set': set, 'slice': slice, 'sorted': sorted,
        'str': str, 'sum': sum, 'tuple': tuple, 'type': type,
        'zip': zip, 'True': True, 'False': False, 'None': None,
    }
    
    # Add math module
    safe_globals = {
        '__builtins__': safe_builtins,
        'math': math,
        'json': json,
        're': re,
    }
    
    # Capture output
    output_buffer = io.StringIO()
    error = None
    
    start_time = time.time()
    
    try:
        with contextlib.redirect_stdout(output_buffer):
            exec(code, safe_globals, {})
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)}"
    
    execution_time_ms = (time.time() - start_time) * 1000
    
    return output_buffer.getvalue(), error, execution_time_ms


# ============== Data Analysis Helpers ==============

def analyze_data(data: List[Any], operation: str) -> Any:
    """Perform basic statistical operations on data."""
    import statistics
    
    # Filter numeric values
    numeric_data = [x for x in data if isinstance(x, (int, float))]
    
    if operation == "mean":
        return statistics.mean(numeric_data)
    elif operation == "median":
        return statistics.median(numeric_data)
    elif operation == "mode":
        return statistics.mode(numeric_data)
    elif operation == "std":
        return statistics.stdev(numeric_data) if len(numeric_data) > 1 else 0
    elif operation == "variance":
        return statistics.variance(numeric_data) if len(numeric_data) > 1 else 0
    elif operation == "sum":
        return sum(numeric_data)
    elif operation == "min":
        return min(numeric_data)
    elif operation == "max":
        return max(numeric_data)
    elif operation == "count":
        return len(data)
    elif operation == "describe":
        if not numeric_data:
            return {"count": len(data), "numeric_values": 0}
        return {
            "count": len(data),
            "numeric_values": len(numeric_data),
            "sum": sum(numeric_data),
            "mean": statistics.mean(numeric_data),
            "median": statistics.median(numeric_data),
            "min": min(numeric_data),
            "max": max(numeric_data),
            "std": statistics.stdev(numeric_data) if len(numeric_data) > 1 else 0
        }
    else:
        raise ValueError(f"Unknown operation: {operation}")


# ============== Unit Conversions ==============

UNIT_CONVERSIONS = {
    # Length (base: meters)
    "m": 1.0,
    "km": 1000.0,
    "cm": 0.01,
    "mm": 0.001,
    "mi": 1609.344,
    "ft": 0.3048,
    "in": 0.0254,
    "yd": 0.9144,
    
    # Mass (base: grams)
    "g": 1.0,
    "kg": 1000.0,
    "mg": 0.001,
    "lb": 453.592,
    "oz": 28.3495,
    
    # Temperature conversions handled separately
    
    # Time (base: seconds)
    "s": 1.0,
    "ms": 0.001,
    "min": 60.0,
    "h": 3600.0,
    "d": 86400.0,
    "wk": 604800.0,
    
    # Data (base: bytes)
    "B": 1.0,
    "KB": 1024.0,
    "MB": 1048576.0,
    "GB": 1073741824.0,
    "TB": 1099511627776.0,
}


def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    """Convert between units."""
    # Handle temperature separately
    if from_unit.lower() in ('c', 'celsius', 'f', 'fahrenheit', 'k', 'kelvin'):
        return convert_temperature(value, from_unit, to_unit)
    
    from_unit = from_unit.upper() if from_unit.upper() in UNIT_CONVERSIONS else from_unit.lower()
    to_unit = to_unit.upper() if to_unit.upper() in UNIT_CONVERSIONS else to_unit.lower()
    
    # Normalize unit names
    unit_aliases = {
        'meter': 'm', 'meters': 'm',
        'kilometer': 'km', 'kilometers': 'km',
        'mile': 'mi', 'miles': 'mi',
        'foot': 'ft', 'feet': 'ft',
        'inch': 'in', 'inches': 'in',
        'gram': 'g', 'grams': 'g',
        'kilogram': 'kg', 'kilograms': 'kg',
        'pound': 'lb', 'pounds': 'lb',
        'ounce': 'oz', 'ounces': 'oz',
        'second': 's', 'seconds': 's',
        'minute': 'min', 'minutes': 'min',
        'hour': 'h', 'hours': 'h',
        'day': 'd', 'days': 'd',
        'week': 'wk', 'weeks': 'wk',
        'byte': 'B', 'bytes': 'B',
    }
    
    from_unit = unit_aliases.get(from_unit.lower(), from_unit)
    to_unit = unit_aliases.get(to_unit.lower(), to_unit)
    
    if from_unit not in UNIT_CONVERSIONS or to_unit not in UNIT_CONVERSIONS:
        raise ValueError(f"Unknown unit: {from_unit} or {to_unit}")
    
    # Convert to base unit, then to target unit
    base_value = value * UNIT_CONVERSIONS[from_unit]
    result = base_value / UNIT_CONVERSIONS[to_unit]
    
    return result


def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Convert between temperature units."""
    from_unit = from_unit.lower()
    to_unit = to_unit.lower()
    
    # Normalize
    if from_unit in ('c', 'celsius'):
        from_unit = 'c'
    elif from_unit in ('f', 'fahrenheit'):
        from_unit = 'f'
    elif from_unit in ('k', 'kelvin'):
        from_unit = 'k'
        
    if to_unit in ('c', 'celsius'):
        to_unit = 'c'
    elif to_unit in ('f', 'fahrenheit'):
        to_unit = 'f'
    elif to_unit in ('k', 'kelvin'):
        to_unit = 'k'
    
    # Convert to Celsius first
    if from_unit == 'f':
        celsius = (value - 32) * 5/9
    elif from_unit == 'k':
        celsius = value - 273.15
    else:
        celsius = value
    
    # Convert from Celsius to target
    if to_unit == 'f':
        return celsius * 9/5 + 32
    elif to_unit == 'k':
        return celsius + 273.15
    else:
        return celsius


# ============== API Endpoints ==============

@app.post("/math/evaluate", response_model=MathResult)
async def evaluate_math(request: MathExpressionRequest):
    """
    Evaluate a mathematical expression safely.
    
    Supports: +, -, *, /, **, %, //, sqrt, sin, cos, tan, log, etc.
    """
    try:
        result = safe_eval_math(request.expression)
        return MathResult(
            expression=request.expression,
            result=result
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation error: {str(e)}")


@app.post("/code/execute", response_model=CodeExecutionResult)
async def execute_code(request: CodeExecutionRequest):
    """
    Execute code in a sandboxed environment.
    
    Currently only supports Python.
    """
    if request.language.lower() != "python":
        raise HTTPException(
            status_code=400,
            detail=f"Language not supported: {request.language}. Only Python is available."
        )
    
    output, error, exec_time = execute_python_safe(request.code, request.timeout)
    
    return CodeExecutionResult(
        output=output,
        error=error,
        execution_time_ms=exec_time
    )


@app.post("/data/analyze")
async def analyze(request: DataAnalysisRequest):
    """
    Perform statistical analysis on data.
    
    Operations: mean, median, mode, std, variance, sum, min, max, count, describe
    """
    try:
        result = analyze_data(request.data, request.operation)
        return {
            "operation": request.operation,
            "data_count": len(request.data),
            "result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@app.post("/datetime")
async def datetime_operations(request: DateTimeRequest):
    """
    Perform date/time operations.
    
    Operations:
    - now: Get current datetime
    - format: Format a datetime string
    - diff: Calculate difference between dates
    - add: Add time to a date
    """
    from datetime import timedelta
    
    try:
        if request.operation == "now":
            fmt = request.format or "%Y-%m-%d %H:%M:%S"
            return {
                "datetime": datetime.now().strftime(fmt),
                "timestamp": datetime.now().timestamp()
            }
            
        elif request.operation == "format":
            if not request.value:
                raise HTTPException(status_code=400, detail="Value required for format")
            
            dt = datetime.fromisoformat(request.value.replace('Z', '+00:00'))
            fmt = request.format or "%Y-%m-%d %H:%M:%S"
            return {"formatted": dt.strftime(fmt)}
            
        elif request.operation == "diff":
            if not request.value or not request.format:
                raise HTTPException(status_code=400, detail="Two dates required")
            
            dt1 = datetime.fromisoformat(request.value.replace('Z', '+00:00'))
            dt2 = datetime.fromisoformat(request.format.replace('Z', '+00:00'))
            diff = dt2 - dt1
            
            return {
                "days": diff.days,
                "seconds": diff.total_seconds(),
                "hours": diff.total_seconds() / 3600
            }
            
        elif request.operation == "add":
            if not request.value or not request.amount or not request.unit:
                raise HTTPException(status_code=400, detail="Value, amount, and unit required")
            
            dt = datetime.fromisoformat(request.value.replace('Z', '+00:00'))
            
            unit_map = {
                'days': timedelta(days=request.amount),
                'hours': timedelta(hours=request.amount),
                'minutes': timedelta(minutes=request.amount),
                'seconds': timedelta(seconds=request.amount),
                'weeks': timedelta(weeks=request.amount)
            }
            
            if request.unit not in unit_map:
                raise HTTPException(status_code=400, detail=f"Unknown unit: {request.unit}")
            
            result = dt + unit_map[request.unit]
            fmt = request.format or "%Y-%m-%d %H:%M:%S"
            
            return {"result": result.strftime(fmt)}
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {request.operation}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DateTime error: {str(e)}")


@app.post("/units/convert")
async def convert(request: UnitConversionRequest):
    """
    Convert between units.
    
    Supports: length, mass, time, temperature, data storage
    """
    try:
        result = convert_units(request.value, request.from_unit, request.to_unit)
        return {
            "original": f"{request.value} {request.from_unit}",
            "converted": f"{result} {request.to_unit}",
            "value": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")


@app.get("/units/supported")
async def get_supported_units():
    """List supported units for conversion."""
    return {
        "length": ["m", "km", "cm", "mm", "mi", "ft", "in", "yd"],
        "mass": ["g", "kg", "mg", "lb", "oz"],
        "time": ["s", "ms", "min", "h", "d", "wk"],
        "temperature": ["C", "F", "K"],
        "data": ["B", "KB", "MB", "GB", "TB"]
    }


# ============== Random/UUID Generation ==============

@app.get("/random/number")
async def random_number(
    min_val: float = 0,
    max_val: float = 100,
    count: int = 1,
    integer: bool = True
):
    """Generate random numbers."""
    import random
    
    if integer:
        numbers = [random.randint(int(min_val), int(max_val)) for _ in range(count)]
    else:
        numbers = [random.uniform(min_val, max_val) for _ in range(count)]
    
    return {"numbers": numbers if count > 1 else numbers[0]}


@app.get("/random/uuid")
async def random_uuid(count: int = 1, version: int = 4):
    """Generate UUID(s)."""
    import uuid
    
    if version == 4:
        uuids = [str(uuid.uuid4()) for _ in range(count)]
    elif version == 1:
        uuids = [str(uuid.uuid1()) for _ in range(count)]
    else:
        raise HTTPException(status_code=400, detail="UUID version must be 1 or 4")
    
    return {"uuids": uuids if count > 1 else uuids[0]}


@app.get("/random/string")
async def random_string(
    length: int = 10,
    charset: str = "alphanumeric"
):
    """Generate random string."""
    import random
    import string
    
    if charset == "alphanumeric":
        chars = string.ascii_letters + string.digits
    elif charset == "alpha":
        chars = string.ascii_letters
    elif charset == "numeric":
        chars = string.digits
    elif charset == "hex":
        chars = string.hexdigits.lower()
    else:
        chars = charset  # Use custom charset
    
    result = ''.join(random.choice(chars) for _ in range(length))
    return {"string": result}


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "generaltask-agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8017)
