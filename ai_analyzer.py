"""
AI-Enhanced Code Analysis Module
Provides intelligent code understanding using OpenAI's GPT models

Performance optimizations:
- Single consolidated API call per file (replaces 2-6 separate calls)
- Parallel file analysis using ThreadPoolExecutor
- Content-hash caching to skip unchanged files
- Smart truncation preserving imports, signatures, and key logic
- Retry with exponential backoff for transient failures
"""

import os
import json
import logging
import re
import time
import hashlib
import threading
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_content_hash_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()

MAX_PARALLEL_WORKERS = 3
MAX_FILES_TO_ANALYZE = 20
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
SMART_TRUNCATION_LIMIT = 5000


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def smart_truncate(content: str, max_chars: int = SMART_TRUNCATION_LIMIT) -> str:
    if len(content) <= max_chars:
        return content

    lines = content.split('\n')

    import_lines = []
    signature_lines = []
    body_lines = []
    import_patterns = re.compile(
        r'^\s*(import |from |require\(|const .* = require|#include|using |package )')
    sig_patterns = re.compile(
        r'^\s*(def |class |function |async function |export |interface |struct |enum |type |const |let |var |public |private |protected |@)')

    for i, line in enumerate(lines):
        if import_patterns.match(line):
            import_lines.append(line)
        elif sig_patterns.match(line):
            ctx_start = max(0, i - 1)
            ctx_end = min(len(lines), i + 3)
            signature_lines.extend(lines[ctx_start:ctx_end])
        else:
            body_lines.append(line)

    result_parts = []
    imports_text = '\n'.join(import_lines)
    result_parts.append(imports_text)
    budget = max_chars - len(imports_text) - 50

    sigs_text = '\n'.join(signature_lines)
    if len(sigs_text) <= budget * 0.4:
        result_parts.append(sigs_text)
        budget -= len(sigs_text)
    else:
        trimmed = sigs_text[:int(budget * 0.4)]
        result_parts.append(trimmed)
        budget -= len(trimmed)

    body_text = '\n'.join(body_lines)
    if len(body_text) <= budget:
        result_parts.append(body_text)
    else:
        result_parts.append(body_text[:budget])

    result = '\n'.join(result_parts)
    if len(result) > max_chars:
        result = result[:max_chars]

    return result + "\n... (truncated)"


def compress_code(content: str) -> str:
    content = re.sub(r'//.*?\n', '\n', content)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'#.*?\n', '\n', content)
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
    content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)

    lines = content.split('\n')
    compressed_lines = []
    for line in lines:
        if line.strip():
            leading_spaces = len(line) - len(line.lstrip())
            indent_level = leading_spaces // 4
            compressed_lines.append('\t' * indent_level + line.lstrip())
        else:
            compressed_lines.append('')

    content = '\n'.join(compressed_lines)
    return content.strip()


def _call_with_retry(func, *args, max_retries=MAX_RETRIES, **kwargs):
    last_error = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            is_transient = any(keyword in error_str for keyword in [
                'rate_limit', 'rate limit', 'timeout', 'timed out',
                'connection', 'server_error', '503', '502', '429'
            ])
            if is_transient and attempt < max_retries - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Transient error (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay}s: {str(e)[:100]}")
                time.sleep(delay)
            else:
                raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry failed with no error captured")


class AICodeAnalyzer:
    """AI-powered code analysis using OpenAI's GPT models"""

    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(
            api_key=api_key,
            timeout=120.0,
            max_retries=1
        )
        self.model = "gpt-4o-mini"

    def analyze_file_consolidated(self, code_content: str, filename: str,
                                   language: str) -> Dict[str, Any]:
        content_hash = compute_content_hash(code_content)
        cache_key = f"{filename}:{content_hash}"
        with _cache_lock:
            if cache_key in _content_hash_cache:
                logger.info(f"Cache hit for {filename}, skipping API call")
                return _content_hash_cache[cache_key]

        try:
            compressed = compress_code(code_content)
            truncated = smart_truncate(compressed)

            prompt = f"""Analyze this {language} code file '{filename}' and provide a comprehensive analysis in JSON format:

```{language}
{truncated}
```

Provide a JSON response with this exact structure:
{{
    "structure": {{
        "functions": [
            {{"name": "function_name", "line": 10, "type": "function"}}
        ],
        "classes": [
            {{"name": "ClassName", "line": 5, "type": "class"}}
        ],
        "imports": [
            {{"module": "module_name", "items": ["item1", "item2"]}}
        ],
        "apis": [
            {{"endpoint": "/api/path", "method": "GET", "line": 100}}
        ],
        "http_calls": [
            {{"url": "/api/other-service/resource", "method": "GET", "line": 55}}
        ]
    }},
    "quality_metrics": {{
        "complexity": "low|medium|high",
        "maintainability": "1-10",
        "test_coverage": "estimated percentage or unknown",
        "code_smells": ["smell1", "smell2"],
        "best_practices": ["practice1", "practice2"],
        "security_issues": ["issue1", "issue2"]
    }},
    "insights": {{
        "what_it_does": "Clear explanation of what this code accomplishes",
        "observations": [
            "Key observation about code structure",
            "Notable patterns or approaches used"
        ],
        "recommendations": [
            "Specific improvement suggestion with rationale",
            "Best practice that could be applied"
        ],
        "complexity_level": "Low|Medium|High",
        "code_quality_score": 75,
        "main_functions": ["function1", "function2"],
        "potential_issues": ["issue1", "issue2"],
        "performance_notes": "Performance-related observations",
        "code_smells": [
            {{
                "smell": "Descriptive name of the code smell",
                "severity": "High|Medium|Low",
                "line": 42,
                "description": "Clear explanation of what the issue is",
                "impact": "How this affects reliability, performance, or functionality",
                "remediation": "Specific steps to fix this issue"
            }}
        ]
    }}
}}

Field extraction rules:

apis — endpoints this file DECLARES/EXPOSES (routes registered by this service):
- C#: combine [Route("api/[controller]")] on the class with [HttpGet/HttpPost/...] on methods; resolve [controller] to the actual controller class name (e.g. CustomerController -> "customer"). Result: "/api/customer/{{id}}/summary"
- Java/Kotlin: combine @RequestMapping on class with @GetMapping/@PostMapping etc. on methods
- Go: path strings passed to router.HandleFunc / mux.Handle / gin.GET etc.
- JS/TS: Express app.get/post/put/delete path strings; Next.js route file paths
- All languages: use the concrete resolved path, not raw attribute text

http_calls — outbound HTTP requests this file MAKES to external/other services:
- C#: HttpClient.GetAsync/PostAsync/PutAsync/DeleteAsync/SendAsync, RestClient.Execute, WebClient.DownloadString
- Java/Kotlin: RestTemplate.getForObject/postForObject, WebClient.get/post, OkHttpClient, Retrofit interface calls, Feign client calls, Ktor HttpClient.get/post
- JavaScript/TypeScript: fetch(url), axios.get/post/put/delete, XMLHttpRequest.open, superagent.get/post
- Go: http.Get(url), http.Post(url), http.NewRequest, http.Client.Do
- Rust: reqwest::get, reqwest::Client::post, hyper::Client::request
- Swift: URLSession.dataTask(with:), URLSession.shared.data(from:)
- C/C++: curl_easy_setopt(curl, CURLOPT_URL, ...), curl_easy_perform
Extract the URL string (or template) and the HTTP method. If the URL is a variable, use its last assigned literal value. Leave http_calls empty ([]) if this file makes no outbound HTTP calls.

For code_smells severity levels:
- High: Greatly improves application reliability, performance, or functional delivery
- Medium: Improves application reliability, performance, or functional delivery
- Low: Nice to have improvements

Be thorough in extracting all functions, classes, imports, API endpoints, and outbound HTTP calls.
Focus on practical, actionable insights."""

            def _make_api_call():
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=[{
                        "role": "system",
                        "content": "You are an expert code analyst. Provide comprehensive code analysis combining structure extraction and quality insights. Respond in valid JSON format."
                    }, {
                        "role": "user",
                        "content": prompt
                    }],
                    response_format={"type": "json_object"},
                    max_completion_tokens=2000)

            response = _call_with_retry(_make_api_call)
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from AI model")

            result = json.loads(content)
            structure = result.get("structure", {})
            quality = result.get("quality_metrics", {})
            insights = result.get("insights", {})

            consolidated = {
                "functions": structure.get("functions", []),
                "classes": structure.get("classes", []),
                "imports": structure.get("imports", []),
                "apis": structure.get("apis", []),
                "http_calls": structure.get("http_calls", []),
                "quality_metrics": quality,
                "content": code_content,
                "language": language,
                "filename": filename,
                "line_count": len(code_content.splitlines()) if code_content else 0,
                "insights": insights
            }

            with _cache_lock:
                _content_hash_cache[cache_key] = consolidated
            return consolidated

        except Exception as e:
            logger.error(f"Error in consolidated analysis for {filename}: {str(e)}")
            return {
                "functions": [],
                "classes": [],
                "imports": [],
                "apis": [],
                "http_calls": [],
                "quality_metrics": {},
                "content": code_content,
                "language": language,
                "filename": filename,
                "line_count": len(code_content.splitlines()) if code_content else 0,
                "insights": {
                    "what_it_does": f"Analysis failed for {filename}",
                    "observations": ["AI analysis temporarily unavailable"],
                    "recommendations": ["Please check API configuration"],
                    "complexity_level": "Unknown",
                    "code_quality_score": 0,
                    "main_functions": [],
                    "potential_issues": ["Analysis error"],
                    "performance_notes": "Analysis unavailable",
                    "code_smells": []
                },
                "error": str(e)
            }

    def extract_code_structure(self, code_content: str, filename: str,
                               language: str) -> Dict[str, Any]:
        return self.analyze_file_consolidated(code_content, filename, language)

    def analyze_single_file(self, code_content: str, filename: str,
                            language: str) -> Dict[str, Any]:
        consolidated = self.analyze_file_consolidated(code_content, filename, language)
        insights = consolidated.get("insights", {})
        if consolidated.get("error"):
            return {
                "status": "error",
                "error": consolidated["error"],
                "analysis": insights
            }
        return {
            "status": "success",
            "analysis": insights,
            "confidence": "high"
        }

    def analyze_code_intent(self, code_content: str, filename: str,
                            language: str) -> Dict[str, Any]:
        return self.analyze_single_file(code_content, filename, language)

    def generate_code_summary(self, code_content: str, filename: str,
                              language: str) -> Dict[str, Any]:
        consolidated = self.analyze_file_consolidated(code_content, filename, language)
        insights = consolidated.get("insights", {})
        what_it_does = insights.get("what_it_does", f"Code file: {filename}")
        observations = insights.get("observations", [])
        summary_parts = [what_it_does]
        for obs in observations:
            summary_parts.append(f"- {obs}")
        summary = "\n".join(summary_parts)
        return {
            "status": "success" if not consolidated.get("error") else "timeout",
            "summary": summary,
            "word_count": len(summary.split())
        }

    def detect_code_patterns(self, code_content: str,
                             language: str) -> Dict[str, Any]:
        consolidated = self.analyze_file_consolidated(
            code_content, "unknown", language)
        insights = consolidated.get("insights", {})
        quality = consolidated.get("quality_metrics", {})
        return {
            "status": "success" if not consolidated.get("error") else "error",
            "patterns": {
                "design_patterns": [],
                "architectural_patterns": [],
                "coding_practices": {
                    "good": quality.get("best_practices", []),
                    "concerns": quality.get("security_issues", [])
                },
                "code_smells": insights.get("code_smells", []),
                "suggestions": insights.get("recommendations", [])
            }
        }

    def analyze_data_flow(self, code_content: str, filename: str,
                          language: str) -> Dict[str, Any]:
        consolidated = self.analyze_file_consolidated(code_content, filename, language)
        insights = consolidated.get("insights", {})
        return {
            "status": "success" if not consolidated.get("error") else "error",
            "data_flow": {
                "input_sources": [],
                "data_transformations": [],
                "output_destinations": [],
                "data_types": [],
                "validation_points": [],
                "potential_data_issues": insights.get("potential_issues", [])
            }
        }

    def generate_comprehensive_analysis(
            self, code_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            code_summary = []
            for file_data in code_files[:20]:
                summary = {
                    "filename": file_data.get("filename", "unknown"),
                    "language": file_data.get("language", "unknown"),
                    "functions": len(file_data.get("functions", [])),
                    "classes": len(file_data.get("classes", [])),
                    "lines": file_data.get("line_count", 0)
                }
                code_summary.append(summary)

            prompt = f"""Analyze this codebase structure and provide comprehensive insights in JSON format:

Codebase Summary:
{json.dumps(code_summary, indent=2)}

Provide analysis:
{{
    "architecture_assessment": "Overall architectural approach and quality",
    "technology_stack": ["technologies", "frameworks", "libraries"],
    "project_type": "web_app|api|library|script|microservice|monolith",
    "maturity_level": "prototype|development|production_ready|enterprise",
    "maintainability_score": "1-10 with explanation",
    "scalability_considerations": ["factor1", "factor2"],
    "team_recommendations": {{
        "skill_requirements": ["required skills"],
        "development_practices": ["recommended practices"],
        "knowledge_gaps": ["areas needing attention"]
    }},
    "modernization_opportunities": ["upgrade1", "upgrade2"],
    "risk_assessment": {{
        "technical_debt": "low|medium|high",
        "security_risks": ["risk1", "risk2"],
        "performance_risks": ["risk1", "risk2"]
    }}
}}
"""

            def _make_api_call():
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=[{
                        "role": "system",
                        "content": "You are a senior software architect performing a comprehensive codebase review. Provide strategic insights in JSON format."
                    }, {
                        "role": "user",
                        "content": prompt
                    }],
                    response_format={"type": "json_object"},
                    max_completion_tokens=1200)

            response = _call_with_retry(_make_api_call)
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from AI model")
            result = json.loads(content)
            return {
                "status": "success",
                "comprehensive_analysis": result,
                "files_analyzed": len(code_files)
            }

        except Exception as e:
            logger.error(f"Error generating comprehensive analysis: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "comprehensive_analysis": None
            }


def _analyze_worker(analyzer: AICodeAnalyzer, file_info: Dict[str, Any]) -> Dict[str, Any]:
    try:
        analysis = analyzer.analyze_file_consolidated(
            file_info["content"], file_info["filename"], file_info["language"])
        logger.info(f"Successfully analyzed {file_info['filename']}")
        return {"filename": file_info["filename"], "analysis": analysis, "error": None}
    except Exception as e:
        logger.error(f"Error analyzing {file_info['filename']}: {str(e)}")
        return {"filename": file_info["filename"], "analysis": None, "error": str(e)}


def _extract_file_info(code_files: List[Any]) -> List[Dict[str, Any]]:
    return [{
        "filename": cf.filename,
        "content": cf.content,
        "language": cf.language,
        "line_count": cf.line_count or 0,
        "size": len(cf.content) if cf.content else 0
    } for cf in code_files]


def analyze_files_individually(code_files: List[Any]) -> Dict[str, Any]:
    try:
        analyzer = AICodeAnalyzer()
        file_analyses = {}

        file_infos = _extract_file_info(code_files)

        workers = min(MAX_PARALLEL_WORKERS, len(file_infos))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(_analyze_worker, analyzer, fi)
                for fi in file_infos
            ]

            for future in as_completed(futures):
                result = future.result()
                fname = result["filename"]
                analysis = result["analysis"]
                error = result["error"]

                fi = next(f for f in file_infos if f["filename"] == fname)

                if analysis and not analysis.get("error"):
                    insights = analysis.get("insights", {})
                    file_analyses[fname] = {
                        "analysis": {
                            "status": "success",
                            "analysis": insights,
                            "confidence": "high"
                        },
                        "language": fi["language"],
                        "size": fi["size"],
                        "lines": fi["line_count"]
                    }
                else:
                    err_msg = error or (analysis.get("error", "Unknown error") if analysis else "Unknown error")
                    insights = analysis.get("insights", {}) if analysis else {}
                    file_analyses[fname] = {
                        "analysis": {
                            "status": "error",
                            "error": err_msg,
                            "analysis": insights if insights else {
                                "what_it_does": f"Analysis failed for {fname}",
                                "observations": ["AI analysis unavailable"],
                                "recommendations": ["Check file content and try again"],
                                "complexity_level": "Unknown",
                                "code_quality_score": 0,
                                "code_smells": []
                            }
                        },
                        "language": fi["language"],
                        "size": fi["size"],
                        "lines": fi["line_count"]
                    }

        return {
            "status": "success",
            "file_analyses": file_analyses,
            "total_files": len(code_files),
            "successful_analyses": len([
                f for f in file_analyses.values()
                if f.get("analysis", {}).get("status") == "success"
            ])
        }

    except Exception as e:
        logger.error(f"Error in file-by-file analysis: {str(e)}")
        return {"status": "error", "error": str(e), "file_analyses": {}}


def analyze_code(code_files: List[Any], save_fn: Optional[Any] = None) -> Dict[str, Any]:
    """
    Analyze files in parallel and update each CodeFile's in-memory fields.

    If `save_fn` is provided, it is called as `save_fn(code_file_id, analysis, error)`
    right after each file finishes, persisting results incrementally so a transient DB
    hiccup near the end of a large run only risks the current file, not the whole batch.
    """
    try:
        analyzer = AICodeAnalyzer()
        results = {}

        total_functions = 0
        total_classes = 0
        total_imports = 0
        total_apis = 0
        languages = set()

        file_infos = _extract_file_info(code_files)
        file_map = {cf.filename: cf for cf in code_files}

        workers = min(MAX_PARALLEL_WORKERS, len(file_infos))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(_analyze_worker, analyzer, fi)
                for fi in file_infos
            ]

            for future in as_completed(futures):
                result = future.result()
                fname = result["filename"]
                analysis = result["analysis"]
                error = result["error"]
                code_file = file_map[fname]

                if analysis and not error:
                    code_file.functions = analysis.get('functions', [])
                    code_file.classes = analysis.get('classes', [])
                    code_file.imports = analysis.get('imports', [])
                    code_file.apis = analysis.get('apis', [])
                    code_file.http_calls = analysis.get('http_calls', [])
                    code_file.quality_metrics = analysis.get('quality_metrics', {})

                    results[fname] = analysis

                    total_functions += len(analysis.get('functions', []))
                    total_classes += len(analysis.get('classes', []))
                    total_imports += len(analysis.get('imports', []))
                    total_apis += len(analysis.get('apis', []))

                    logger.info(f"Successfully analyzed {fname}")

                    if save_fn is not None:
                        try:
                            save_fn(code_file.id, analysis, None)
                        except Exception as save_err:
                            logger.error(f"Incremental save failed for {fname}: {save_err}")
                else:
                    logger.error(f"Error analyzing {fname}: {error}")
                    results[fname] = {
                        'error': error,
                        'functions': [],
                        'classes': [],
                        'imports': [],
                        'apis': [],
                        'http_calls': [],
                        'quality_metrics': {},
                        'content': code_file.content,
                        'language': code_file.language,
                        'filename': fname,
                        'line_count': len(code_file.content.splitlines()) if code_file.content else 0
                    }

                    code_file.functions = []
                    code_file.classes = []
                    code_file.imports = []
                    code_file.apis = []
                    code_file.http_calls = []
                    code_file.quality_metrics = {}

                    if save_fn is not None:
                        try:
                            save_fn(code_file.id, None, error or "Unknown analysis error")
                        except Exception as save_err:
                            logger.error(f"Incremental save failed for {fname}: {save_err}")

                if code_file.language:
                    languages.add(code_file.language)

        results['_summary'] = {
            'total_files': len(code_files),
            'total_functions': total_functions,
            'total_classes': total_classes,
            'total_imports': total_imports,
            'total_apis': total_apis,
            'languages': sorted(list(languages))
        }

        return results

    except Exception as e:
        logger.error(f"Error in analyze_code: {str(e)}")
        return {}


def analyze_codebase_with_ai(
        analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    try:
        analyzer = AICodeAnalyzer()
        ai_insights = {
            "file_analyses": {},
            "comprehensive_analysis": None,
            "analysis_metadata": {
                "model_used": analyzer.model,
                "timestamp": None,
                "files_processed": 0
            }
        }

        code_files = []
        for filename, file_data in analysis_results.items():
            if filename != "_summary" and isinstance(file_data, dict):
                if "content" in file_data:
                    code_files.append({
                        "filename": filename,
                        "content": file_data["content"],
                        "language": file_data.get("language", "unknown"),
                        "functions": file_data.get("functions", []),
                        "classes": file_data.get("classes", []),
                        "line_count": file_data.get("line_count", 0)
                    })

        for file_data in code_files[:MAX_FILES_TO_ANALYZE]:
            filename = file_data["filename"]
            content = file_data["content"]
            language = file_data["language"]

            logger.info(f"Analyzing {filename} with AI...")
            consolidated = analyzer.analyze_file_consolidated(content, filename, language)
            insights = consolidated.get("insights", {})

            file_analysis = {
                "intent_analysis": {
                    "status": "success" if not consolidated.get("error") else "error",
                    "analysis": insights,
                    "confidence": "high"
                },
                "summary": {
                    "status": "success" if not consolidated.get("error") else "timeout",
                    "summary": insights.get("what_it_does", f"Code file: {filename}"),
                    "word_count": len(insights.get("what_it_does", "").split())
                },
                "patterns": {
                    "status": "success" if not consolidated.get("error") else "error",
                    "patterns": {
                        "design_patterns": [],
                        "architectural_patterns": [],
                        "coding_practices": {
                            "good": consolidated.get("quality_metrics", {}).get("best_practices", []),
                            "concerns": consolidated.get("quality_metrics", {}).get("security_issues", [])
                        },
                        "code_smells": insights.get("code_smells", []),
                        "suggestions": insights.get("recommendations", [])
                    }
                },
                "data_flow": {
                    "status": "success" if not consolidated.get("error") else "error",
                    "data_flow": {
                        "input_sources": [],
                        "data_transformations": [],
                        "output_destinations": [],
                        "data_types": [],
                        "validation_points": [],
                        "potential_data_issues": insights.get("potential_issues", [])
                    }
                }
            }

            ai_insights["file_analyses"][filename] = file_analysis

        ai_insights["comprehensive_analysis"] = analyzer.generate_comprehensive_analysis(code_files)
        ai_insights["analysis_metadata"]["files_processed"] = len(code_files)
        from datetime import datetime
        ai_insights["analysis_metadata"]["timestamp"] = datetime.utcnow().isoformat() + "Z"

        return ai_insights

    except Exception as e:
        logger.error(f"Error in AI codebase analysis: {str(e)}")
        return {"error": str(e), "status": "failed"}
