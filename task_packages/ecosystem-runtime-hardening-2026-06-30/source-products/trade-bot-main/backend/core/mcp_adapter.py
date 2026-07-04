"""
MCP Adapter - Wrapper for orchestrator integration
Provides tool-style interfaces for stock prediction system
"""

import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from stock_analysis_complete import (
    EnhancedDataIngester,
    FeatureEngineer,
    predict_stock_price,
    train_ml_models,
    DATA_CACHE_DIR,
    FEATURE_CACHE_DIR,
    MODEL_DIR,
    LOGS_DIR
)
from live_price_validator import LivePriceValidator

logger = logging.getLogger(__name__)

# Request/Response logging
MCP_LOG_DIR = LOGS_DIR / "mcp_requests"
MCP_LOG_DIR.mkdir(parents=True, exist_ok=True)


class MCPAdapter:
    """
    MCP-style adapter for stock prediction system
    Provides orchestrator-friendly tool interfaces with comprehensive logging
    """
    
    def __init__(self):
        self.ingester = EnhancedDataIngester()
        self.engineer = FeatureEngineer()
        self.price_validator = LivePriceValidator()
        self.request_counter = 0
        
    def _log_request(self, tool_name: str, request_data: Dict) -> str:
        """Log incoming request"""
        self.request_counter += 1
        request_id = f"{tool_name}_{int(time.time())}_{self.request_counter}"
        
        log_entry = {
            "request_id": request_id,
            "tool": tool_name,
            "timestamp": datetime.now().isoformat(),
            "request": request_data
        }
        
        log_file = MCP_LOG_DIR / f"{datetime.now().strftime('%Y%m%d')}_requests.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        logger.info(f"MCP Request [{request_id}]: {tool_name}")
        return request_id
    
    def _convert_to_json_serializable(self, obj):
        """Recursively convert numpy types and other non-JSON-serializable types to Python native types"""
        import numpy as np
        
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_to_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Try to convert to string as fallback
            try:
                return str(obj)
            except:
                return obj
    
    def _log_response(self, request_id: str, response_data: Dict, duration_ms: float):
        """Log outgoing response"""
        # Convert numpy types to Python native types for JSON serialization
        sanitized_response = self._convert_to_json_serializable(response_data)
        
        log_entry = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": duration_ms,
            "response": sanitized_response
        }
        
        log_file = MCP_LOG_DIR / f"{datetime.now().strftime('%Y%m%d')}_responses.jsonl"
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except TypeError as e:
            logger.error(f"Failed to log response: {e}")
            logger.error(f"Problematic data: {log_entry}")
            # Try to log with default=str as fallback
            try:
                with open(log_file, 'a') as f:
                    f.write(json.dumps(log_entry, default=str) + '\n')
            except Exception as e2:
                logger.error(f"Failed to log response even with default=str: {e2}")
        
        logger.info(f"MCP Response [{request_id}]: {duration_ms:.2f}ms")
    
    def predict(
        self,
        symbols: List[str],
        horizon: str = "intraday",
        risk_profile: Optional[str] = None,
        stop_loss_pct: Optional[float] = None,
        capital_risk_pct: Optional[float] = None,
        drawdown_limit_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        MCP Tool: predict
        
        Args:
            symbols: List of stock symbols to predict
            horizon: Time horizon (intraday, short, long)
            risk_profile: Optional risk profile override
        
        Returns:
            Dict with metadata and predictions array
        """
        start_time = time.time()
        request_data = {
            "symbols": symbols,
            "horizon": horizon,
            "risk_profile": risk_profile
        }
        request_id = self._log_request("predict", request_data)
        
        try:
            predictions = []
            
            for symbol in symbols:
                try:
                    print(f"\n{'='*80}", flush=True)
                    print(f"[API REQUEST] Processing {symbol} for {horizon} horizon", flush=True)
                    print(f"{'='*80}\n", flush=True)
                    logger.info(f"[{request_id}] Predicting {symbol} ({horizon})")
                    
                    # STEP 1: Ensure data exists
                    json_path = DATA_CACHE_DIR / f"{symbol}_all_data.json"
                    
                    if not json_path.exists():
                        print(f"[STEP 1/4] Data not found for {symbol}. Fetching price data (fast path)...", flush=True)
                        logger.info(f"[{request_id}] Data not found for {symbol}. Fetching...")
                        try:
                            self.ingester.fetch_price_only(symbol, period="2y")
                            print(f"[STEP 1/4] [OK] Data fetched successfully!\n", flush=True)
                            logger.info(f"[{request_id}] Data fetched for {symbol}")
                        except Exception as e:
                            print(f"[STEP 1/4] [FAIL] Failed to fetch data: {e}\n", flush=True)
                            logger.error(f"[{request_id}] Failed to fetch data for {symbol}: {e}")
                            predictions.append({
                                "symbol": symbol,
                                "horizon": horizon,
                                "error": f"Data fetch failed: {str(e)}"
                            })
                            continue
                    else:
                        print(f"[STEP 1/4] [OK] Data already cached\n", flush=True)
                    
                    # STEP 2: Ensure features are calculated
                    features_path = FEATURE_CACHE_DIR / f"{symbol}_features.json"
                    if not features_path.exists():
                        print(f"[STEP 2/4] Features not found. Calculating 50+ technical indicators...", flush=True)
                        logger.info(f"[{request_id}] Features not found for {symbol}. Calculating...")
                        print("[pipe] load_all_data...", flush=True)
                        all_data = self.ingester.load_all_data(symbol)
                        print("[pipe] load_all_data done", flush=True)
                        if all_data:
                            df = all_data.get('price_history')
                            if df is not None and not df.empty:
                                print("[pipe] calculate_all_features...", flush=True)
                                features_df = self.engineer.calculate_all_features(df, symbol)
                                print("[pipe] calculate_all_features done", flush=True)
                                print("[pipe] save_features...", flush=True)
                                self.engineer.save_features(features_df, symbol)
                                print("[pipe] save_features done", flush=True)
                                print(f"[STEP 2/4] [OK] Features calculated successfully!\n", flush=True)
                                logger.info(f"[{request_id}] Features calculated for {symbol}")
                    
                    else:
                        print(f"[STEP 2/4] [OK] Features already calculated\n", flush=True)
                    
                    # STEP 3: Check if models exist for this horizon
                    model_files = list(MODEL_DIR.glob(f"{symbol}_{horizon}_*"))
                    
                    if not model_files:
                        print(f"[STEP 3/4] Models not found. Training 4 ML models (RF+LGB+XGB+DQN)...", flush=True)
                        print(f"            This will take 60-90 seconds...\n", flush=True)
                        logger.info(f"[{request_id}] Models not found for {symbol} ({horizon}). Training...")
                        try:
                            print("[pipe] train_ml_models...", flush=True)
                            from stock_analysis_complete import train_ml_models
                            training_result = train_ml_models(symbol, horizon, verbose=True)
                            print("[pipe] train_ml_models done", flush=True)
                            
                            # Handle both dict and bool return formats
                            success = training_result.get('success', False) if isinstance(training_result, dict) else training_result
                            
                            if not success:
                                print(f"[STEP 3/4] [FAIL] Training failed\n", flush=True)
                                logger.error(f"[{request_id}] Training failed for {symbol}")
                                predictions.append({
                                    "symbol": symbol,
                                    "horizon": horizon,
                                    "error": "Model training failed"
                                })
                                continue
                            print(f"[STEP 3/4] [OK] All 4 models trained successfully!\n", flush=True)
                            logger.info(f"[{request_id}] Models trained for {symbol} ({horizon})")
                        except Exception as e:
                            print(f"[STEP 3/4] [FAIL] Training error: {e}\n", flush=True)
                            logger.error(f"[{request_id}] Training failed for {symbol}: {e}", exc_info=True)
                            predictions.append({
                                "symbol": symbol,
                                "horizon": horizon,
                                "error": f"Training failed: {str(e)}"
                            })
                            continue
                    else:
                        print(f"[STEP 3/4] [OK] Models already trained\n", flush=True)
                    
                    # STEP 4: Get prediction
                    print(f"[STEP 4/4] Generating prediction using ensemble of 4 models...", flush=True)
                    print("[pipe] predict_stock_price...", flush=True)
                    prediction = predict_stock_price(symbol, horizon=horizon, verbose=True)
                    print("[pipe] predict_stock_price done", flush=True)
                    print(f"[STEP 4/4] [OK] Prediction generated!\n", flush=True)
                    
                    if prediction:
                        # ENFORCE LIVE PRICE: Replace cached price with live price
                        print(f"[VALIDATION] Enforcing live price validation...", flush=True)
                        prediction = self.price_validator.enforce_live_price_in_prediction(prediction, symbol)
                        
                        # Override risk_profile if specified
                        if risk_profile:
                            prediction["risk_profile"] = risk_profile
                            prediction["horizon_details"]["risk_profile"] = risk_profile
                        
                        predictions.append(prediction)
                        
                        # Log to main predictions file
                        self._log_prediction_to_file(prediction)
                        
                        logger.info(f"[{request_id}] [OK] {symbol}: {prediction['action']} "
                                  f"(confidence: {prediction['confidence']:.4f})")
                    else:
                        logger.warning(f"[{request_id}] [FAIL] {symbol}: No prediction returned")
                        predictions.append({
                            "symbol": symbol,
                            "horizon": horizon,
                            "error": "Prediction failed - models may need training"
                        })
                        
                except Exception as e:
                    logger.error(f"[{request_id}] Error predicting {symbol}: {e}", exc_info=True)
                    predictions.append({
                        "symbol": symbol,
                        "horizon": horizon,
                        "error": str(e)
                    })
            
            # Determine risk profile from horizon if not specified
            if not risk_profile:
                risk_profiles = {
                    "intraday": "high",
                    "short": "moderate",
                    "long": "low"
                }
                risk_profile = risk_profiles.get(horizon, "moderate")
            
            response = {
                "metadata": {
                    "count": len(predictions),
                    "horizon": horizon,
                    "risk_profile": risk_profile,
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id
                },
                "predictions": predictions
            }
            
            # Inject DataStatus for frontend compatibility
            # Derived from the first prediction's validation data if available
            db_status = "CACHED_YAHOO_FINANCE"
            freshness = 0
            market = "NORMAL"
            
            if predictions and "price_metadata" in predictions[0]:
                meta = predictions[0]["price_metadata"]
                if meta.get("price_source") == "yahoo_finance_live":
                    db_status = "REALTIME_YAHOO_FINANCE"
                    
                # Calculate freshness in seconds
                if "price_timestamp" in meta:
                    try:
                        pt = datetime.fromisoformat(meta["price_timestamp"])
                        freshness = (datetime.now() - pt).total_seconds()
                    except:
                        pass
                        
                if meta.get("market_state") == "CLOSED":
                    market = "MARKET_CLOSED"
                elif meta.get("market_state") == "PRE" or meta.get("market_state") == "POST":
                    market = "EVENT_WINDOW"
                    
            data_status_obj = {
                "data_source": db_status,
                "data_freshness_seconds": int(freshness),
                "market_context": market
            }
            
            # Add to each prediction if not present
            for p in predictions:
                if "data_status" not in p:
                    p["data_status"] = data_status_obj
            
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, response, duration_ms)
            
            return response
            
        except Exception as e:
            logger.error(f"[{request_id}] Critical error: {e}", exc_info=True)
            error_response = {
                "metadata": {
                    "request_id": request_id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                "predictions": []
            }
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, error_response, duration_ms)
            return error_response
    
    def scan_all(
        self,
        symbols: Optional[List[str]] = None,
        horizon: str = "intraday",
        min_confidence: float = 0.5,
        stop_loss_pct: Optional[float] = None,
        capital_risk_pct: Optional[float] = None,
        drawdown_limit_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        MCP Tool: scan_all
        
        Batch scoring of multiple symbols with filtering and risk parameters
        
        Args:
            symbols: List of symbols to scan (uses default universe if None)
            horizon: Time horizon for predictions
            min_confidence: Minimum confidence threshold for shortlist
        
        Returns:
            Dict with shortlisted high-confidence predictions
        """
        start_time = time.time()
        
        # Default universe if no symbols provided
        if not symbols:
            symbols = [
                "RPOWER.NS", "HDFCBANK.NS", "INFY.NS", "TCS.NS", 
                "RELIANCE.NS", "TATASTEEL.NS", "WIPRO.NS", "ITC.NS",
                "AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "META"
            ]
        
        request_data = {
            "symbols": symbols,
            "horizon": horizon,
            "min_confidence": min_confidence
        }
        request_id = self._log_request("scan_all", request_data)
        
        try:
            logger.info(f"[{request_id}] Scanning {len(symbols)} symbols...")
            
            all_predictions = []
            shortlist = []
            
            for symbol in symbols:
                try:
                    print(f"\n{'='*80}", flush=True)
                    print(f"[SCAN] Processing {symbol} ({len(symbols)} total)", flush=True)
                    print(f"{'='*80}\n", flush=True)
                    logger.info(f"[{request_id}] Processing {symbol}...")
                    
                    # STEP 1: Ensure data exists
                    json_path = DATA_CACHE_DIR / f"{symbol}_all_data.json"
                    
                    if not json_path.exists():
                        print(f"[STEP 1/4] Fetching price data (fast path)...", flush=True)
                        logger.info(f"[{request_id}] Data not found for {symbol}. Fetching...")
                        try:
                            self.ingester.fetch_price_only(symbol, period="2y")
                            print(f"[STEP 1/4] [OK] Data fetched!\n", flush=True)
                            logger.info(f"[{request_id}] Data fetched for {symbol}")
                        except Exception as e:
                            print(f"[STEP 1/4] [FAIL] Fetch failed: {e}\n", flush=True)
                            logger.error(f"[{request_id}] Failed to fetch data for {symbol}: {e}")
                            continue
                    else:
                        print(f"[STEP 1/4] [OK] Data cached\n", flush=True)
                    
                    # STEP 2: Ensure features are calculated
                    features_path = FEATURE_CACHE_DIR / f"{symbol}_features.json"
                    if not features_path.exists():
                        print(f"[STEP 2/4] Calculating 50+ technical indicators...", flush=True)
                        logger.info(f"[{request_id}] Features not found for {symbol}. Calculating...")
                        all_data = self.ingester.load_all_data(symbol)
                        if all_data:
                            df = all_data.get('price_history')
                            if df is not None and not df.empty:
                                features_df = self.engineer.calculate_all_features(df, symbol)
                                self.engineer.save_features(features_df, symbol)
                                print(f"[STEP 2/4] [OK] Features calculated!\n", flush=True)
                                logger.info(f"[{request_id}] Features calculated for {symbol}")
                    
                    else:
                        print(f"[STEP 2/4] [OK] Features cached\n", flush=True)
                    
                    # STEP 3: Check if models exist for this horizon
                    model_files = list(MODEL_DIR.glob(f"{symbol}_{horizon}_*"))
                    
                    if not model_files:
                        print(f"[STEP 3/4] Training 4 ML models (60-90 seconds)...", flush=True)
                        logger.info(f"[{request_id}] Models not found for {symbol} ({horizon}). Training...")
                        try:
                            from stock_analysis_complete import train_ml_models
                            training_result = train_ml_models(symbol, horizon, verbose=True)
                            
                            # Handle both dict and bool return formats
                            success = training_result.get('success', False) if isinstance(training_result, dict) else training_result
                            
                            if not success:
                                print(f"[STEP 3/4] [FAIL] Training failed\n", flush=True)
                                logger.error(f"[{request_id}] Training failed for {symbol}")
                                continue
                            print(f"[STEP 3/4] [OK] Models trained!\n", flush=True)
                            logger.info(f"[{request_id}] Models trained for {symbol} ({horizon})")
                        except Exception as e:
                            print(f"[STEP 3/4] [FAIL] Training error: {e}\n", flush=True)
                            logger.error(f"[{request_id}] Training failed for {symbol}: {e}", exc_info=True)
                            continue
                    else:
                        print(f"[STEP 3/4] [OK] Models cached\n", flush=True)
                    
                    # STEP 4: Get prediction
                    print(f"[STEP 4/4] Generating prediction...", flush=True)
                    prediction = predict_stock_price(symbol, horizon=horizon, verbose=True)
                    print(f"[STEP 4/4] [OK] Done!\n", flush=True)
                    
                    if prediction:
                        all_predictions.append(prediction)
                        
                        # Add to shortlist if meets confidence threshold
                        if prediction.get('confidence', 0) >= min_confidence:
                            shortlist.append(prediction)
                            logger.info(f"[{request_id}] [OK] SHORTLIST: {symbol} "
                                      f"({prediction['action']}, conf: {prediction['confidence']:.4f})")
                        
                        # Log prediction
                        self._log_prediction_to_file(prediction)
                        
                except Exception as e:
                    logger.error(f"[{request_id}] Error scanning {symbol}: {e}")
            
            # Sort shortlist by score (descending)
            shortlist.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            response = {
                "metadata": {
                    "total_scanned": len(symbols),
                    "predictions_generated": len(all_predictions),
                    "shortlist_count": len(shortlist),
                    "horizon": horizon,
                    "min_confidence": min_confidence,
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id
                },
                "shortlist": shortlist,
                "all_predictions": all_predictions
            }
            
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, response, duration_ms)
            
            logger.info(f"[{request_id}] Scan complete: {len(shortlist)}/{len(all_predictions)} "
                       f"passed threshold ({duration_ms:.2f}ms)")
            
            return response
            
        except Exception as e:
            logger.error(f"[{request_id}] Scan error: {e}", exc_info=True)
            error_response = {
                "metadata": {
                    "error": str(e),
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                },
                "shortlist": [],
                "all_predictions": []
            }
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, error_response, duration_ms)
            return error_response
    
    def analyze(
        self,
        symbol: str,
        horizons: Optional[List[str]] = None,
        stop_loss_pct: Optional[float] = None,
        capital_risk_pct: Optional[float] = None,
        drawdown_limit_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        MCP Tool: analyze
        
        Deep analysis of a single ticker across multiple horizons
        
        Args:
            symbol: Stock symbol to analyze
            horizons: List of horizons to analyze (default: all 3)
        
        Returns:
            Dict with multi-horizon analysis
        """
        start_time = time.time()
        
        if not horizons:
            horizons = ["intraday", "short", "long"]
        
        request_data = {
            "symbol": symbol,
            "horizons": horizons
        }
        request_id = self._log_request("analyze", request_data)
        
        try:
            logger.info(f"[{request_id}] Analyzing {symbol} across {len(horizons)} horizons...")
            
            predictions = []
            
            # First ensure data and features exist (only once, not per horizon)
            json_path = DATA_CACHE_DIR / f"{symbol}_all_data.json"
            
            if not json_path.exists():
                print(f"\n[ANALYZE] Fetching data for {symbol}...", flush=True)
                logger.info(f"[{request_id}] Data not found for {symbol}. Fetching...")
                try:
                    self.ingester.fetch_price_only(symbol, period="2y")
                    print(f"[ANALYZE] [OK] Data fetched!\n", flush=True)
                except Exception as e:
                    print(f"[ANALYZE] [FAIL] Data fetch failed: {e}\n", flush=True)
                    logger.error(f"[{request_id}] Failed to fetch data: {e}")
                    return {
                        "metadata": {
                            "symbol": symbol,
                            "error": f"Data fetch failed: {str(e)}",
                            "request_id": request_id,
                            "timestamp": datetime.now().isoformat()
                        },
                        "predictions": []
                    }
            else:
                print(f"[ANALYZE] [OK] Data cached for {symbol}\n", flush=True)
            
            # Ensure features are calculated
            features_path = FEATURE_CACHE_DIR / f"{symbol}_features.json"
            if not features_path.exists():
                print(f"[ANALYZE] Calculating features for {symbol}...", flush=True)
                logger.info(f"[{request_id}] Features not found. Calculating...")
                all_data = self.ingester.load_all_data(symbol)
                if all_data:
                    df = all_data.get('price_history')
                    if df is not None and not df.empty:
                        features_df = self.engineer.calculate_all_features(df, symbol)
                        self.engineer.save_features(features_df, symbol)
                        print(f"[ANALYZE] [OK] Features calculated!\n", flush=True)
            else:
                print(f"[ANALYZE] [OK] Features cached for {symbol}\n", flush=True)
            
            # Now process each horizon
            for horizon in horizons:
                try:
                    print(f"\n{'='*80}", flush=True)
                    print(f"[ANALYZE] Processing {symbol} - {horizon.upper()} horizon", flush=True)
                    print(f"{'='*80}\n", flush=True)
                    
                    # Check if models exist for this horizon
                    model_files = list(MODEL_DIR.glob(f"{symbol}_{horizon}_*"))
                    
                    if not model_files:
                        print(f"[ANALYZE] Training models for {horizon} horizon (60-90 seconds)...", flush=True)
                        logger.info(f"[{request_id}] Models not found for {symbol} ({horizon}). Training...")
                        try:
                            from stock_analysis_complete import train_ml_models
                            training_result = train_ml_models(symbol, horizon, verbose=True)
                            
                            # Handle both dict and bool return formats
                            success = training_result.get('success', False) if isinstance(training_result, dict) else training_result
                            
                            if not success:
                                print(f"[ANALYZE] [FAIL] Training failed for {horizon}\n", flush=True)
                                logger.error(f"[{request_id}] Training failed for {horizon}")
                                predictions.append({
                                    "symbol": symbol,
                                    "horizon": horizon,
                                    "error": "Model training failed"
                                })
                                continue
                            print(f"[ANALYZE] [OK] Models trained for {horizon}!\n", flush=True)
                        except Exception as e:
                            print(f"[ANALYZE] [FAIL] Training error: {e}\n", flush=True)
                            logger.error(f"[{request_id}] Training error for {horizon}: {e}", exc_info=True)
                            predictions.append({
                                "symbol": symbol,
                                "horizon": horizon,
                                "error": f"Training failed: {str(e)}"
                            })
                            continue
                    else:
                        print(f"[ANALYZE] [OK] Models exist for {horizon}\n", flush=True)
                    
                    # Generate prediction
                    print(f"[ANALYZE] Generating {horizon} prediction...", flush=True)
                    prediction = predict_stock_price(symbol, horizon=horizon, verbose=True)
                    
                    if prediction:
                        print(f"[ANALYZE] [OK] {horizon} prediction: {prediction['action']} "
                              f"({prediction['predicted_return']:+.2f}%, conf: {prediction['confidence']:.4f})\n", flush=True)
                        predictions.append(prediction)
                        self._log_prediction_to_file(prediction)
                        logger.info(f"[{request_id}] [OK] {horizon}: {prediction['action']} "
                                  f"(conf: {prediction['confidence']:.4f})")
                    else:
                        print(f"[ANALYZE] [FAIL] {horizon} prediction failed\n", flush=True)
                        logger.warning(f"[{request_id}] [FAIL] {horizon}: No prediction")
                        predictions.append({
                            "symbol": symbol,
                            "horizon": horizon,
                            "error": "Prediction failed"
                        })
                        
                except Exception as e:
                    print(f"[ANALYZE] [FAIL] Error on {horizon}: {e}\n", flush=True)
                    logger.error(f"[{request_id}] Error on {horizon}: {e}")
                    predictions.append({
                        "symbol": symbol,
                        "horizon": horizon,
                        "error": str(e)
                    })
            
            # Calculate consensus across horizons
            actions = [p.get('action') for p in predictions if 'action' in p]
            avg_confidence = sum(p.get('confidence', 0) for p in predictions if 'confidence' in p) / len(predictions) if predictions else 0
            
            consensus = None
            if len(set(actions)) == 1:
                consensus = f"Strong {actions[0]} - All horizons agree"
            elif actions.count('LONG') > actions.count('SHORT'):
                consensus = "Bullish - Majority LONG signals"
            elif actions.count('SHORT') > actions.count('LONG'):
                consensus = "Bearish - Majority SHORT signals"
            else:
                consensus = "Mixed signals - Exercise caution"
            
            response = {
                "metadata": {
                    "symbol": symbol,
                    "horizons": horizons,
                    "count": len(predictions),
                    "average_confidence": round(avg_confidence, 4),
                    "consensus": consensus,
                    "risk_parameters": {
                        "stop_loss_pct": stop_loss_pct,
                        "capital_risk_pct": capital_risk_pct,
                        "drawdown_limit_pct": drawdown_limit_pct
                    },
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id
                },
                "predictions": predictions
            }
            
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, response, duration_ms)
            
            logger.info(f"[{request_id}] Analysis complete: {consensus} ({duration_ms:.2f}ms)")
            
            return response
            
        except Exception as e:
            logger.error(f"[{request_id}] Analysis error: {e}", exc_info=True)
            error_response = {
                "metadata": {
                    "symbol": symbol,
                    "error": str(e),
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                },
                "predictions": []
            }
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, error_response, duration_ms)
            return error_response
    
    def train_rl(
        self,
        symbol: str,
        horizon: str = "intraday",
        n_episodes: Optional[int] = None,
        force_retrain: bool = False
    ) -> Dict[str, Any]:
        """
        MCP Tool: train_rl
        
        Train or retrain the DQN (Reinforcement Learning) agent
        
        Args:
            symbol: Stock symbol to train on
            horizon: Time horizon - "intraday" (1 day), "short" (5 days), or "long" (30 days)
            n_episodes: Number of training episodes (None = auto-use all available data)
            force_retrain: Force retraining even if model already exists
        
        Returns:
            Dict with training status and performance metrics
        """
        start_time = time.time()
        request_data = {
            "symbol": symbol,
            "horizon": horizon,
            "n_episodes": n_episodes,
            "force_retrain": force_retrain
        }
        request_id = self._log_request("train_rl", request_data)
        
        try:
            logger.info(f"[{request_id}] RL training requested for {symbol} ({horizon})")
            
            # Check if model already exists
            model_path = MODEL_DIR / f"{symbol}_{horizon}_dqn_agent.pt"
            
            if model_path.exists() and not force_retrain:
                logger.info(f"[{request_id}] Model exists, skipping (use force_retrain=true to override)")
                response = {
                    "status": "skipped",
                    "message": f"Model already exists for {symbol} ({horizon}). Use force_retrain=true to retrain.",
                    "model_path": str(model_path),
                    "symbol": symbol,
                    "horizon": horizon,
                    "timestamp": datetime.now().isoformat()
                }
                duration_ms = (time.time() - start_time) * 1000
                self._log_response(request_id, response, duration_ms)
                return response
            
            # STEP 1: Ensure data exists
            logger.info(f"[{request_id}] Ensuring data exists for {symbol}...")
            json_path = DATA_CACHE_DIR / f"{symbol}_all_data.json"
            
            if not json_path.exists():
                logger.info(f"[{request_id}] Data not found. Fetching price data (fast path)...")
                try:
                    self.ingester.fetch_price_only(symbol, period="2y")
                    logger.info(f"[{request_id}] Data fetched successfully")
                except Exception as e:
                    logger.error(f"[{request_id}] Data fetch failed: {e}")
                    error_response = {
                        "status": "error",
                        "error": f"Failed to fetch data: {str(e)}",
                        "symbol": symbol,
                        "horizon": horizon
                    }
                    duration_ms = (time.time() - start_time) * 1000
                    self._log_response(request_id, error_response, duration_ms)
                    return error_response
            
            # STEP 2: Ensure features are calculated
            logger.info(f"[{request_id}] Ensuring features are calculated...")
            features_path = FEATURE_CACHE_DIR / f"{symbol}_features.json"
            if not features_path.exists():
                logger.info(f"[{request_id}] Features not found. Calculating...")
                all_data = self.ingester.load_all_data(symbol)
                if all_data:
                    df = all_data.get('price_history')
                    if df is not None and not df.empty:
                        features_df = self.engineer.calculate_all_features(df, symbol)
                        self.engineer.save_features(features_df, symbol)
                        logger.info(f"[{request_id}] Features calculated successfully")
            
            # STEP 3: Train all models (includes DQN)
            logger.info(f"[{request_id}] Starting training for horizon: {horizon}")
            from stock_analysis_complete import train_ml_models, DQNTradingAgent
            
            training_result = train_ml_models(symbol, horizon, verbose=True)
            
            # Handle both old (bool) and new (dict) return formats
            if isinstance(training_result, dict):
                success = training_result.get('success', False)
                metrics = training_result.get('dqn_metrics', {})
            else:
                success = training_result
                metrics = {}
            
            if not success:
                logger.error(f"[{request_id}] Training failed")
                error_response = {
                    "status": "failed",
                    "message": "Model training failed. Check if data/features exist.",
                    "symbol": symbol,
                    "horizon": horizon
                }
                duration_ms = (time.time() - start_time) * 1000
                self._log_response(request_id, error_response, duration_ms)
                return error_response
            
            # STEP 4: Use metrics from training (or load if not available)
            if not metrics:
                logger.info(f"[{request_id}] Metrics not in training result, loading agent...")
                try:
                    from stock_analysis_complete import DQNTradingAgent
                    dqn_agent = DQNTradingAgent(n_features=1)  # Will be updated when loading
                    dqn_agent.load(symbol, horizon)
                    metrics = dqn_agent._calculate_performance_metrics()
                except Exception as e:
                    logger.warning(f"[{request_id}] Could not load metrics: {e}")
                    metrics = {}
            
            # Build response with metrics
            model_path = MODEL_DIR / f"{symbol}_{horizon}_dqn_agent.pt"
            
            # Get model info - try to load agent for dimensions
            n_features = 81  # Default
            n_actions = 3
            try:
                if metrics:
                    # Metrics available, try to get agent info
                    from stock_analysis_complete import DQNTradingAgent
                    temp_agent = DQNTradingAgent(n_features=1)
                    temp_agent.load(symbol, horizon)
                    n_features = temp_agent.n_features
                    n_actions = temp_agent.n_actions
            except:
                pass
            
            response = {
                "status": "success",
                "message": f"RL agent trained successfully for {symbol} ({horizon})",
                "symbol": symbol,
                "horizon": horizon,
                "horizon_details": {
                    "intraday": {"days": 1, "description": "Same day / Next day"},
                    "short": {"days": 5, "description": "1 week (Swing trading)"},
                    "long": {"days": 30, "description": "1 month (Position trading)"}
                }.get(horizon, {"days": 1, "description": "Unknown"}),
                "training_metrics": {
                    "total_episodes": metrics.get('total_episodes', 0),
                    "cumulative_reward": round(float(metrics.get('cumulative_reward', 0)), 4),
                    "average_reward": round(float(metrics.get('average_reward', 0)), 6),
                    "sharpe_ratio": round(float(metrics.get('sharpe_ratio', 0)), 4),
                    "win_rate": round(float(metrics.get('win_rate', 0)), 4),
                    "final_epsilon": round(float(metrics.get('epsilon', 0)), 4),
                    "buffer_size": metrics.get('buffer_size', 0)
                },
                "model_info": {
                    "model_path": str(model_path),
                    "model_type": "DQN (Deep Q-Network)",
                    "n_features": n_features,
                    "n_actions": n_actions
                },
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id
            }
            
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, response, duration_ms)
            
            logger.info(f"[{request_id}] RL training successful: {metrics.get('total_episodes', 0)} episodes, "
                      f"Sharpe: {metrics.get('sharpe_ratio', 0):.4f}, Win Rate: {metrics.get('win_rate', 0):.2%}")
            
            return response
            
        except Exception as e:
            logger.error(f"[{request_id}] RL training error: {e}", exc_info=True)
            error_response = {
                "status": "error",
                "error": str(e),
                "symbol": symbol,
                "horizon": horizon,
                "timestamp": datetime.now().isoformat()
            }
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, error_response, duration_ms)
            return error_response
    
    def fetch_data(
        self,
        symbols: List[str],
        period: str = "2y",
        force_refresh: bool = False,
        refresh: bool = False,
        include_features: bool = False
    ) -> Dict[str, Any]:
        """
        MCP Tool: fetch_data
        
        Fetch historical data for multiple symbols from Yahoo Finance
        
        Args:
            symbols: List of stock symbols to fetch
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, max)
            force_refresh: Force refresh even if cached (legacy parameter)
            refresh: Force refresh even if cached (maps to force_refresh)
            include_features: Also calculate and include technical features
            period: Data period - "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"
            force_refresh: Force refresh even if cached data exists
        
        Returns:
            Dict with fetch status for each symbol
        """
        start_time = time.time()
        
        # Map 'refresh' parameter to 'force_refresh' for compatibility
        if refresh:
            force_refresh = True
        
        request_data = {
            "symbols": symbols,
            "period": period,
            "refresh": refresh,
            "include_features": include_features
        }
        request_id = self._log_request("fetch_data", request_data)
        
        try:
            print(f"\n{'='*80}", flush=True)
            print(f"[FETCH DATA] Fetching data for {len(symbols)} symbol(s)", flush=True)
            print(f"  Period: {period}", flush=True)
            print(f"  Include Features: {include_features}", flush=True)
            print(f"  Force Refresh: {force_refresh}", flush=True)
            print(f"{'='*80}\n", flush=True)
            
            logger.info(f"[{request_id}] Fetching data for {len(symbols)} symbol(s)")
            
            results = []
            
            for symbol in symbols:
                try:
                    print(f"[{symbol}] Processing...", flush=True)
                    logger.info(f"[{request_id}] Processing {symbol}...")
                    
                    # Check if data already exists
                    json_path = DATA_CACHE_DIR / f"{symbol}_all_data.json"
                    
                    if json_path.exists() and not force_refresh:
                        # Load existing data to get metadata
                        print(f"[{symbol}] Data cached, loading...", flush=True)
                        all_data = self.ingester.load_all_data(symbol)
                        if all_data:
                            df = all_data.get('price_history')
                            if df is not None and not df.empty:
                                result_entry = {
                                    "symbol": symbol,
                                    "status": "cached",
                                    "message": "Data already cached",
                                    "rows": len(df),
                                    "date_range": {
                                        "start": str(df.index[0]),
                                        "end": str(df.index[-1])
                                    },
                                    "latest_price": round(float(df['Close'].iloc[-1]), 2)
                                }
                                
                                # If include_features is true, calculate and include features
                                if include_features:
                                    print(f"[{symbol}] Calculating features...", flush=True)
                                    features_path = FEATURE_CACHE_DIR / f"{symbol}_features.json"
                                    
                                    if features_path.exists():
                                        # Load existing features
                                        with open(features_path, 'r') as f:
                                            features_data = json.load(f)
                                        result_entry["features"] = {
                                            "status": "loaded",
                                            "total_features": features_data.get('total_features', 0),
                                            "feature_file": str(features_path)
                                        }
                                        print(f"[{symbol}] Features loaded from cache", flush=True)
                                    else:
                                        # Calculate fresh features
                                        features_df = self.engineer.calculate_all_features(df, symbol)
                                        self.engineer.save_features(features_df, symbol)
                                        result_entry["features"] = {
                                            "status": "calculated",
                                            "total_features": len(features_df.columns),
                                            "feature_file": str(features_path)
                                        }
                                        print(f"[{symbol}] Features calculated and saved", flush=True)
                                
                                results.append(result_entry)
                                print(f"[{symbol}] [OK] Complete\n", flush=True)
                                logger.info(f"[{request_id}] {symbol}: Using cached data ({len(df)} rows)")
                                continue
                    
                    # Fetch fresh data
                    print(f"[{symbol}] Fetching from Yahoo Finance...", flush=True)
                    logger.info(f"[{request_id}] {symbol}: Fetching from Yahoo Finance...")
                    all_data = self.ingester.fetch_all_data(symbol, period=period)
                    
                    if all_data:
                        df = all_data.get('price_history')
                        if df is not None and not df.empty:
                            print(f"[{symbol}] [OK] Data fetched: {len(df)} rows", flush=True)
                            
                            result_entry = {
                                "symbol": symbol,
                                "status": "success",
                                "message": "Data fetched successfully",
                                "rows": len(df),
                                "date_range": {
                                    "start": str(df.index[0]),
                                    "end": str(df.index[-1])
                                },
                                "latest_price": round(float(df['Close'].iloc[-1]), 2),
                                "cache_path": str(json_path)
                            }
                            
                            # If include_features is true, calculate and include features
                            if include_features:
                                print(f"[{symbol}] Calculating 50+ technical indicators...", flush=True)
                                features_df = self.engineer.calculate_all_features(df, symbol)
                                self.engineer.save_features(features_df, symbol)
                                features_path = FEATURE_CACHE_DIR / f"{symbol}_features.json"
                                result_entry["features"] = {
                                    "status": "calculated",
                                    "total_features": len(features_df.columns),
                                    "feature_file": str(features_path)
                                }
                                print(f"[{symbol}] [OK] Features calculated: {len(features_df.columns)} indicators", flush=True)
                            
                            results.append(result_entry)
                            print(f"[{symbol}] [OK] Complete\n", flush=True)
                            logger.info(f"[{request_id}] {symbol}: Fetched {len(df)} rows")
                        else:
                            results.append({
                                "symbol": symbol,
                                "status": "error",
                                "message": "No price history data received"
                            })
                    else:
                        results.append({
                            "symbol": symbol,
                            "status": "error",
                            "message": "Failed to fetch data from Yahoo Finance"
                        })
                        
                except Exception as e:
                    logger.error(f"[{request_id}] Error fetching {symbol}: {e}")
                    results.append({
                        "symbol": symbol,
                        "status": "error",
                        "message": str(e)
                    })
            
            # Summary
            successful = len([r for r in results if r['status'] == 'success'])
            cached = len([r for r in results if r['status'] == 'cached'])
            failed = len([r for r in results if r['status'] == 'error'])
            
            response = {
                "metadata": {
                    "total_symbols": len(symbols),
                    "successful": successful,
                    "cached": cached,
                    "failed": failed,
                    "period": period,
                    "include_features": include_features,
                    "force_refresh": force_refresh,
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id
                },
                "results": results
            }
            
            print(f"\n[FETCH DATA] Summary:", flush=True)
            print(f"  Total: {len(symbols)}, Success: {successful}, Cached: {cached}, Failed: {failed}", flush=True)
            print(f"  Features included: {include_features}\n", flush=True)
            
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, response, duration_ms)
            
            logger.info(f"[{request_id}] Fetch complete: {successful} success, {cached} cached, {failed} failed")
            
            return response
            
        except Exception as e:
            logger.error(f"[{request_id}] Fetch data error: {e}", exc_info=True)
            error_response = {
                "metadata": {
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id
                },
                "results": []
            }
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, error_response, duration_ms)
            return error_response
    
    def health(self) -> Dict[str, Any]:
        """
        MCP Tool: health
        
        Service health check with resource usage
        
        Returns:
            Dict with service status and resource information
        """
        start_time = time.time()
        request_id = self._log_request("health", {})
        
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            # Count cached symbols
            cached_symbols = len(list(DATA_CACHE_DIR.glob("*_data.parquet"))) if DATA_CACHE_DIR.exists() else 0
            feature_files = len(list(FEATURE_CACHE_DIR.glob("*_features.json"))) if FEATURE_CACHE_DIR.exists() else 0
            model_files = len(list(MODEL_DIR.glob("*.pkl"))) + len(list(MODEL_DIR.glob("*.pt"))) if MODEL_DIR.exists() else 0
            
            response = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id,
                "service": {
                    "name": "Stock Prediction API",
                    "version": "3.0",
                    "uptime_seconds": time.time() - psutil.boot_time()
                },
                "resources": {
                    "cpu_percent": process.cpu_percent(interval=0.1),
                    "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                    "memory_percent": round(process.memory_percent(), 2),
                    "threads": process.num_threads()
                },
                "data": {
                    "cached_symbols": cached_symbols,
                    "feature_files": feature_files,
                    "trained_models": model_files,
                    "cache_dir": str(DATA_CACHE_DIR),
                    "feature_dir": str(FEATURE_CACHE_DIR),
                    "model_dir": str(MODEL_DIR),
                    "logs_dir": str(LOGS_DIR)
                },
                "directories": {
                    "cache_exists": DATA_CACHE_DIR.exists(),
                    "features_exists": FEATURE_CACHE_DIR.exists(),
                    "models_exists": MODEL_DIR.exists(),
                    "logs_exists": LOGS_DIR.exists()
                }
            }
            
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, response, duration_ms)
            
            return response
            
        except Exception as e:
            logger.error(f"[{request_id}] Health check error: {e}", exc_info=True)
            error_response = {
                "status": "degraded",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id
            }
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, error_response, duration_ms)
            return error_response
    
    def process_feedback(
        self,
        symbol: str,
        predicted_action: str,
        user_feedback: str,
        actual_return: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        MCP Tool: process_feedback
        
        Process user feedback for RL fine-tuning
        
        Args:
            symbol: Stock symbol
            predicted_action: The action that was predicted (LONG/SHORT/HOLD)
            user_feedback: User's feedback ('correct' or 'incorrect')
            actual_return: Actual return percentage (optional)
        
        Returns:
            Dict with feedback processing status
        """
        start_time = time.time()
        request_data = {
            "symbol": symbol,
            "predicted_action": predicted_action,
            "user_feedback": user_feedback,
            "actual_return": actual_return
        }
        request_id = self._log_request("feedback", request_data)
        
        try:
            print(f"\n{'='*80}", flush=True)
            print(f"[FEEDBACK] Processing feedback for {symbol}", flush=True)
            print(f"{'='*80}", flush=True)
            print(f"  Predicted Action: {predicted_action}", flush=True)
            print(f"  User Feedback: {user_feedback}", flush=True)
            print(f"  Actual Return: {actual_return}%\n" if actual_return else "  Actual Return: Not provided\n", flush=True)
            
            logger.info(f"[{request_id}] Processing feedback for {symbol}: {user_feedback}")
            
            # Call the provide_feedback function from stock_analysis_complete
            from stock_analysis_complete import provide_feedback, load_feedback_memory
            
            # Save the feedback with validation
            feedback_result = provide_feedback(symbol, predicted_action, user_feedback, actual_return)
            
            # Check if feedback was rejected due to validation error
            if feedback_result.get('status') == 'error':
                error_response = {
                    "status": "error",
                    "error": feedback_result.get('error', 'Feedback validation failed'),
                    "validation_warning": feedback_result.get('validation_warning'),
                    "suggested_feedback": feedback_result.get('suggested_feedback'),
                    "symbol": symbol,
                    "predicted_action": predicted_action,
                    "user_feedback": user_feedback,
                    "actual_return": actual_return,
                    "timestamp": datetime.now().isoformat(),
                    "request_id": request_id
                }
                print(f"[FEEDBACK] [ERROR] Feedback rejected due to validation error!", flush=True)
                print(f"[FEEDBACK] {feedback_result.get('validation_warning', 'Unknown error')}\n", flush=True)
                
                duration_ms = (time.time() - start_time) * 1000
                self._log_response(request_id, error_response, duration_ms)
                logger.warning(f"[{request_id}] Feedback rejected: {feedback_result.get('validation_warning')}")
                
                return error_response
            
            # Load feedback memory to get stats
            feedback_memory = load_feedback_memory()
            
            # Calculate statistics
            total_feedback = len(feedback_memory)
            symbol_feedback = [f for f in feedback_memory if f['symbol'] == symbol]
            correct_count = sum(1 for f in symbol_feedback if f['user_feedback'] == 'correct')
            incorrect_count = sum(1 for f in symbol_feedback if f['user_feedback'] == 'incorrect')
            
            accuracy = (correct_count / len(symbol_feedback) * 100) if symbol_feedback else 0
            
            response = {
                "status": feedback_result.get('status', 'success'),
                "message": f"Feedback recorded for {symbol}",
                "feedback_entry": {
                    "symbol": symbol,
                    "predicted_action": predicted_action,
                    "user_feedback": user_feedback,
                    "actual_return": actual_return,
                    "timestamp": datetime.now().isoformat()
                },
                "validation": {
                    "validation_warning": feedback_result.get('validation_warning'),
                    "suggested_feedback": feedback_result.get('suggested_feedback')
                } if feedback_result.get('validation_warning') else None,
                "statistics": {
                    "total_feedback_count": total_feedback,
                    "symbol_feedback_count": len(symbol_feedback),
                    "correct": correct_count,
                    "incorrect": incorrect_count,
                    "accuracy": round(accuracy, 2)
                },
                "next_steps": {
                    "message": "Feedback saved to memory",
                    "suggestion": "Use /tools/train_rl with force_retrain=true to fine-tune the model with this feedback"
                },
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id
            }
            
            print(f"[FEEDBACK] [OK] Feedback saved successfully!", flush=True)
            print(f"[FEEDBACK] Accuracy for {symbol}: {accuracy:.2f}% ({correct_count}/{len(symbol_feedback)})\n", flush=True)
            
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, response, duration_ms)
            
            logger.info(f"[{request_id}] Feedback processed: {user_feedback} for {symbol}")
            
            return response
            
        except Exception as e:
            print(f"[FEEDBACK] [FAIL] Error: {e}\n", flush=True)
            logger.error(f"[{request_id}] Feedback error: {e}", exc_info=True)
            error_response = {
                "status": "error",
                "error": str(e),
                "symbol": symbol,
                "timestamp": datetime.now().isoformat()
            }
            duration_ms = (time.time() - start_time) * 1000
            self._log_response(request_id, error_response, duration_ms)
            return error_response
    
    def _log_prediction_to_file(self, prediction: Dict):
        """Log prediction to main predictions file"""
        try:
            # Convert numpy types to Python native types for JSON serialization
            sanitized_prediction = self._convert_to_json_serializable(prediction)
            log_file = LOGS_DIR / "mcp_predictions.jsonl"
            with open(log_file, 'a') as f:
                f.write(json.dumps(sanitized_prediction) + '\n')
        except Exception as e:
            logger.error(f"Failed to log prediction: {e}")

