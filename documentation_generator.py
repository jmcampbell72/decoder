"""
Documentation Generator for Code Analysis
Generates comprehensive documentation from analysis results with DOCX export
"""

import json
from datetime import datetime
from typing import Dict, Any, List
import os
import re
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH


class DocumentationGenerator:
    """Generate structured documentation from code analysis results"""
    
    def __init__(self):
        pass
        
    def generate_documentation(self, analysis) -> Dict[str, Any]:
        """Generate structured documentation with comprehensive sections"""
        
        # Extract and organize data from analysis
        doc_data = self._extract_comprehensive_data(analysis)
        
        # Generate structured sections
        sections = {
            'overview': self._generate_code_overview(doc_data),
            'quality_metrics': self._generate_quality_metrics(doc_data),
            'key_components': self._generate_key_components(doc_data),
            'architecture': self._generate_architecture_overview(doc_data),
            'security': self._generate_security_concerns(doc_data),
            'hardcoded_items': self._generate_hardcoded_items(doc_data),
            'file_details': self._generate_file_details(doc_data),
            'recommendations': self._generate_recommendations(doc_data)
        }
        
        return {
            'sections': sections,
            'metadata': {
                'analysis_name': analysis.name,
                'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'total_files': len(analysis.code_files),
                'languages': doc_data['languages'],
                'total_lines': doc_data['total_lines'],
                'analysis_id': analysis.id
            },
            'raw_data': doc_data
        }
    
    def _extract_comprehensive_data(self, analysis) -> Dict[str, Any]:
        """Extract comprehensive data from analysis results"""
        
        data = {
            'languages': set(),
            'total_files': 0,
            'total_lines': 0,
            'functions': [],
            'classes': [],
            'modules': [],
            'apis': [],
            'dependencies': set(),
            'security_issues': [],
            'hardcoded_values': [],
            'quality_metrics': {},
            'file_details': [],
            'complexity_analysis': {}
        }
        
        # Process each file
        for file_obj in analysis.code_files:
            data['total_files'] += 1
            data['total_lines'] += file_obj.line_count or 0
            data['languages'].add(file_obj.language)
            
            # Extract file-specific data
            file_data = {
                'filename': file_obj.filename,
                'language': file_obj.language,
                'lines': file_obj.line_count or 0,
                'functions': file_obj.functions or [],
                'classes': file_obj.classes or [],
                'imports': file_obj.imports or [],
                'apis': file_obj.apis or [],
                'quality': file_obj.quality_metrics or {},
                'content_preview': file_obj.content[:500] if file_obj.content else ""
            }
            
            data['file_details'].append(file_data)
            
            # Aggregate functions and classes
            if file_obj.functions:
                data['functions'].extend(file_obj.functions)
            if file_obj.classes:
                data['classes'].extend(file_obj.classes)
            if file_obj.apis:
                data['apis'].extend(file_obj.apis)
            if file_obj.imports:
                for imp in file_obj.imports:
                    if isinstance(imp, dict) and 'module' in imp:
                        data['dependencies'].add(imp['module'])
            
            # Extract security concerns and hardcoded values
            if file_obj.content:
                data['security_issues'].extend(self._detect_security_issues(file_obj.content, file_obj.filename))
                data['hardcoded_values'].extend(self._detect_hardcoded_values(file_obj.content, file_obj.filename))
        
        # Convert sets to lists for JSON serialization
        data['languages'] = list(data['languages'])
        data['dependencies'] = list(data['dependencies'])
        
        return data
    
    def _generate_code_overview(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code overview section"""
        return {
            'title': 'Code Overview',
            'content': {
                'summary': f"This codebase contains {data['total_files']} files written in {len(data['languages'])} programming language(s).",
                'statistics': {
                    'total_files': data['total_files'],
                    'programming_languages': data['languages'],
                    'total_lines_of_code': data['total_lines'],
                    'modules_components': len(data['file_details']),
                    'functions': len(data['functions']),
                    'classes_structures': len(data['classes']),
                    'data_structures': self._count_data_structures(data),
                    'external_dependencies': len(data['dependencies']),
                    'api_endpoints': len(data['apis'])
                },
                'language_breakdown': self._get_language_breakdown(data),
                'dependency_list': data['dependencies'][:20]  # Top 20 dependencies
            }
        }
    
    def _generate_quality_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code quality metrics section"""
        quality_stats = self._calculate_quality_stats(data)
        
        return {
            'title': 'Code Quality Metrics',
            'content': {
                'overall_score': quality_stats['overall_score'],
                'metrics': {
                    'code_complexity': quality_stats['avg_complexity'],
                    'maintainability_index': quality_stats['maintainability'],
                    'documentation_coverage': quality_stats['documentation_coverage'],
                    'test_coverage': quality_stats.get('test_coverage', 'N/A'),
                    'code_duplication': quality_stats.get('duplication', 'N/A')
                },
                'file_quality_breakdown': quality_stats['file_breakdown'],
                'recommendations': quality_stats['recommendations']
            }
        }
    
    def _generate_key_components(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate key components section"""
        return {
            'title': 'Key Components',
            'content': {
                'core_modules': self._identify_core_modules(data),
                'main_classes': self._get_important_classes(data),
                'critical_functions': self._get_critical_functions(data),
                'entry_points': self._identify_entry_points(data),
                'configuration_files': self._identify_config_files(data),
                'utility_modules': self._identify_utility_modules(data)
            }
        }
    
    def _generate_architecture_overview(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate architecture overview section"""
        return {
            'title': 'Architecture Overview',
            'content': {
                'architectural_pattern': self._detect_architectural_pattern(data),
                'module_structure': self._analyze_module_structure(data),
                'dependency_graph': self._create_dependency_summary(data),
                'design_patterns': self._detect_design_patterns(data),
                'layered_structure': self._analyze_layers(data),
                'coupling_analysis': self._analyze_coupling(data)
            }
        }
    
    def _generate_security_concerns(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate security concerns section"""
        return {
            'title': 'Security Analysis',
            'content': {
                'security_issues': data['security_issues'],
                'vulnerability_summary': self._categorize_security_issues(data['security_issues']),
                'security_recommendations': self._generate_security_recommendations(data['security_issues']),
                'sensitive_data_handling': self._analyze_sensitive_data(data),
                'authentication_patterns': self._detect_auth_patterns(data),
                'encryption_usage': self._detect_encryption_usage(data)
            }
        }
    
    def _generate_hardcoded_items(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate hardcoded items section"""
        return {
            'title': 'Hardcoded Values Analysis',
            'content': {
                'hardcoded_values': data['hardcoded_values'],
                'categories': self._categorize_hardcoded_values(data['hardcoded_values']),
                'risk_assessment': self._assess_hardcoded_risks(data['hardcoded_values']),
                'remediation_suggestions': self._suggest_hardcoded_fixes(data['hardcoded_values'])
            }
        }
    
    def _generate_file_details(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed file analysis section"""
        return {
            'title': 'Detailed File Analysis',
            'content': {
                'files': data['file_details'],
                'complexity_ranking': self._rank_files_by_complexity(data['file_details']),
                'size_analysis': self._analyze_file_sizes(data['file_details']),
                'responsibility_analysis': self._analyze_file_responsibilities(data['file_details'])
            }
        }
    
    def _generate_recommendations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations section"""
        return {
            'title': 'Recommendations & Action Items',
            'content': {
                'priority_actions': self._generate_priority_actions(data),
                'code_improvements': self._generate_code_improvements(data),
                'architecture_suggestions': self._generate_architecture_suggestions(data),
                'security_actions': self._generate_security_actions(data),
                'maintenance_tasks': self._generate_maintenance_tasks(data)
            }
        }
    
    # Helper methods for analysis and detection
    def _detect_security_issues(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Detect potential security issues in code"""
        issues = []
        
        # Common security patterns to look for
        security_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password'),
            (r'api_key\s*=\s*["\'][^"\']+["\']', 'Hardcoded API key'),
            (r'secret\s*=\s*["\'][^"\']+["\']', 'Hardcoded secret'),
            (r'eval\s*\(', 'Use of eval() function'),
            (r'exec\s*\(', 'Use of exec() function'),
            (r'sql\s*=\s*["\'][^"\']*%[^"\']*["\']', 'Potential SQL injection'),
            (r'subprocess\.call\([^)]*shell\s*=\s*True', 'Shell injection risk'),
            (r'pickle\.loads?\(', 'Unsafe deserialization'),
        ]
        
        for pattern, issue_type in security_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append({
                    'type': issue_type,
                    'file': filename,
                    'line': line_num,
                    'context': match.group(0)[:100],
                    'severity': self._assess_security_severity(issue_type)
                })
        
        return issues
    
    def _detect_hardcoded_values(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Detect hardcoded values in code"""
        hardcoded = []
        
        # Patterns for hardcoded values
        patterns = [
            (r'["\']http[s]?://[^"\']+["\']', 'URL'),
            (r'["\'][^"\']*@[^"\']*\.[^"\']+["\']', 'Email'),
            (r'["\'][0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}["\']', 'IP Address'),
            (r'["\'][A-Za-z0-9]{20,}["\']', 'Potential Token/Key'),
            (r'["\'](?:SELECT|INSERT|UPDATE|DELETE)[^"\']*["\']', 'SQL Query'),
            (r'["\'][A-Z0-9_]{10,}["\']', 'Configuration Value'),
        ]
        
        for pattern, value_type in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                hardcoded.append({
                    'type': value_type,
                    'value': match.group(0)[:50],
                    'file': filename,
                    'line': line_num,
                    'risk_level': self._assess_hardcoded_risk(value_type, match.group(0))
                })
        
        return hardcoded
    
    def _assess_security_severity(self, issue_type: str) -> str:
        """Assess security issue severity"""
        high_risk = ['Hardcoded password', 'Hardcoded API key', 'Use of eval()', 'Shell injection risk']
        if issue_type in high_risk:
            return 'High'
        return 'Medium'
    
    def _assess_hardcoded_risk(self, value_type: str, value: str) -> str:
        """Assess risk level of hardcoded values"""
        high_risk = ['Email', 'IP Address', 'Potential Token/Key']
        if value_type in high_risk or len(value) > 30:
            return 'High'
        return 'Medium'
    
    def _count_data_structures(self, data: Dict[str, Any]) -> int:
        """Count data structures (classes, interfaces, etc.)"""
        return len(data['classes'])
    
    def _get_language_breakdown(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Get breakdown of code by language"""
        breakdown = {}
        for file_detail in data['file_details']:
            lang = file_detail['language']
            breakdown[lang] = breakdown.get(lang, 0) + file_detail['lines']
        return breakdown
    
    def _calculate_quality_stats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate code quality statistics"""
        total_files = len(data['file_details'])
        if total_files == 0:
            return {'overall_score': 0, 'avg_complexity': 0, 'maintainability': 0, 'documentation_coverage': 0, 'file_breakdown': [], 'recommendations': []}
        
        complexities = []
        file_breakdown = []
        
        for file_detail in data['file_details']:
            quality = file_detail.get('quality', {})
            complexity = quality.get('cyclomatic_complexity', 1)
            complexities.append(complexity)
            
            file_breakdown.append({
                'filename': file_detail['filename'],
                'complexity': complexity,
                'lines': file_detail['lines'],
                'functions': len(file_detail['functions']),
                'score': min(100, max(0, 100 - complexity * 5))
            })
        
        avg_complexity = sum(complexities) / len(complexities)
        overall_score = max(0, 100 - avg_complexity * 10)
        
        recommendations = []
        if avg_complexity > 5:
            recommendations.append("Consider refactoring complex functions")
        if data['total_lines'] / total_files > 200:
            recommendations.append("Some files are quite large, consider splitting them")
        
        return {
            'overall_score': round(overall_score, 1),
            'avg_complexity': round(avg_complexity, 1),
            'maintainability': round(max(0, 100 - avg_complexity * 8), 1),
            'documentation_coverage': round(len([f for f in data['file_details'] if 'README' in f['filename'] or 'doc' in f['filename'].lower()]) / total_files * 100, 1),
            'file_breakdown': file_breakdown,
            'recommendations': recommendations
        }
    
    def _identify_core_modules(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify core modules in the codebase"""
        core_modules = []
        for file_detail in data['file_details']:
            if (len(file_detail['functions']) > 5 or 
                len(file_detail['classes']) > 2 or
                'main' in file_detail['filename'].lower() or
                'core' in file_detail['filename'].lower()):
                core_modules.append({
                    'name': file_detail['filename'],
                    'functions': len(file_detail['functions']),
                    'classes': len(file_detail['classes']),
                    'importance': 'High' if 'main' in file_detail['filename'].lower() else 'Medium'
                })
        return core_modules[:10]
    
    def _get_important_classes(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get important classes from the codebase"""
        classes = []
        for cls in data['classes'][:10]:
            if isinstance(cls, dict):
                classes.append({
                    'name': cls.get('name', 'Unknown'),
                    'methods': len(cls.get('methods', [])),
                    'properties': len(cls.get('properties', [])),
                    'file': cls.get('file', 'Unknown')
                })
        return classes
    
    def _get_critical_functions(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get critical functions from the codebase"""
        functions = []
        critical_names = ['main', 'init', 'setup', 'configure', 'run', 'execute', 'process']
        
        for func in data['functions'][:15]:
            if isinstance(func, dict):
                name = func.get('name', '').lower()
                is_critical = any(critical in name for critical in critical_names)
                functions.append({
                    'name': func.get('name', 'Unknown'),
                    'parameters': len(func.get('parameters', [])),
                    'file': func.get('file', 'Unknown'),
                    'critical': is_critical
                })
        
        return sorted(functions, key=lambda x: x['critical'], reverse=True)[:10]
    
    def _identify_entry_points(self, data: Dict[str, Any]) -> List[str]:
        """Identify entry points in the codebase"""
        entry_points = []
        for file_detail in data['file_details']:
            filename = file_detail['filename'].lower()
            if any(name in filename for name in ['main', 'index', 'app', 'server', 'run']):
                entry_points.append(file_detail['filename'])
        return entry_points
    
    def _identify_config_files(self, data: Dict[str, Any]) -> List[str]:
        """Identify configuration files"""
        config_files = []
        for file_detail in data['file_details']:
            filename = file_detail['filename'].lower()
            if any(ext in filename for ext in ['config', 'settings', '.env', '.ini', '.yaml', '.yml', '.json', '.toml']):
                config_files.append(file_detail['filename'])
        return config_files
    
    def _identify_utility_modules(self, data: Dict[str, Any]) -> List[str]:
        """Identify utility modules"""
        utility_modules = []
        for file_detail in data['file_details']:
            filename = file_detail['filename'].lower()
            if any(name in filename for name in ['util', 'helper', 'common', 'shared', 'lib']):
                utility_modules.append(file_detail['filename'])
        return utility_modules
    
    def _detect_architectural_pattern(self, data: Dict[str, Any]) -> str:
        """Detect architectural pattern used"""
        filenames = [f['filename'].lower() for f in data['file_details']]
        
        if any('controller' in f for f in filenames) and any('model' in f for f in filenames):
            return 'MVC (Model-View-Controller)'
        elif any('component' in f for f in filenames) and any('service' in f for f in filenames):
            return 'Component-based Architecture'
        elif any('api' in f for f in filenames) and any('route' in f for f in filenames):
            return 'REST API Architecture'
        elif len(data['classes']) > len(data['functions']) * 0.5:
            return 'Object-Oriented Architecture'
        else:
            return 'Procedural/Functional Architecture'
    
    def _analyze_module_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze module structure"""
        return {
            'total_modules': len(data['file_details']),
            'avg_functions_per_module': len(data['functions']) / max(1, len(data['file_details'])),
            'avg_classes_per_module': len(data['classes']) / max(1, len(data['file_details'])),
            'module_sizes': [f['lines'] for f in data['file_details']],
            'largest_module': max(data['file_details'], key=lambda x: x['lines'])['filename'] if data['file_details'] else 'None'
        }
    
    def _create_dependency_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create dependency summary"""
        return {
            'total_dependencies': len(data['dependencies']),
            'external_libraries': [dep for dep in data['dependencies'] if not dep.startswith('.')],
            'internal_modules': [dep for dep in data['dependencies'] if dep.startswith('.')],
            'most_common': data['dependencies'][:10] if data['dependencies'] else []
        }
    
    def _detect_design_patterns(self, data: Dict[str, Any]) -> List[str]:
        """Detect design patterns in the code"""
        patterns = []
        class_names = [cls.get('name', '').lower() for cls in data['classes'] if isinstance(cls, dict)]
        
        if any('factory' in name for name in class_names):
            patterns.append('Factory Pattern')
        if any('singleton' in name for name in class_names):
            patterns.append('Singleton Pattern')
        if any('observer' in name for name in class_names):
            patterns.append('Observer Pattern')
        if any('adapter' in name for name in class_names):
            patterns.append('Adapter Pattern')
        
        return patterns or ['None detected']
    
    def _analyze_layers(self, data: Dict[str, Any]) -> List[str]:
        """Analyze layered structure"""
        layers = []
        filenames = [f['filename'].lower() for f in data['file_details']]
        
        if any('controller' in f for f in filenames):
            layers.append('Presentation Layer (Controllers)')
        if any('service' in f for f in filenames):
            layers.append('Business Logic Layer (Services)')
        if any('model' in f or 'entity' in f for f in filenames):
            layers.append('Data Layer (Models)')
        if any('repository' in f or 'dao' in f for f in filenames):
            layers.append('Data Access Layer')
        
        return layers or ['Single-layer structure']
    
    def _analyze_coupling(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze coupling between modules"""
        total_imports = sum(len(f['imports']) for f in data['file_details'])
        total_files = len(data['file_details'])
        
        return {
            'avg_imports_per_file': round(total_imports / max(1, total_files), 1),
            'coupling_level': 'High' if total_imports / max(1, total_files) > 10 else 'Medium' if total_imports / max(1, total_files) > 5 else 'Low',
            'most_coupled_files': sorted(data['file_details'], key=lambda x: len(x['imports']), reverse=True)[:5]
        }
    
    def _categorize_security_issues(self, issues: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize security issues by type"""
        categories = {}
        for issue in issues:
            issue_type = issue['type']
            categories[issue_type] = categories.get(issue_type, 0) + 1
        return categories
    
    def _generate_security_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """Generate security recommendations"""
        recommendations = []
        if any('password' in issue['type'].lower() for issue in issues):
            recommendations.append("Move hardcoded passwords to environment variables")
        if any('api' in issue['type'].lower() for issue in issues):
            recommendations.append("Store API keys in secure configuration files")
        if any('eval' in issue['type'].lower() for issue in issues):
            recommendations.append("Replace eval() calls with safer alternatives")
        
        return recommendations or ["No specific security issues detected"]
    
    def _analyze_sensitive_data(self, data: Dict[str, Any]) -> List[str]:
        """Analyze sensitive data handling"""
        sensitive_patterns = []
        for file_detail in data['file_details']:
            content = file_detail.get('content_preview', '').lower()
            if any(term in content for term in ['password', 'token', 'secret', 'key']):
                sensitive_patterns.append(f"Potential sensitive data in {file_detail['filename']}")
        
        return sensitive_patterns or ["No obvious sensitive data patterns detected"]
    
    def _detect_auth_patterns(self, data: Dict[str, Any]) -> List[str]:
        """Detect authentication patterns"""
        auth_patterns = []
        for file_detail in data['file_details']:
            content = file_detail.get('content_preview', '').lower()
            if 'login' in content or 'auth' in content:
                auth_patterns.append(f"Authentication logic in {file_detail['filename']}")
        
        return auth_patterns or ["No authentication patterns detected"]
    
    def _detect_encryption_usage(self, data: Dict[str, Any]) -> List[str]:
        """Detect encryption usage"""
        encryption_usage = []
        for file_detail in data['file_details']:
            content = file_detail.get('content_preview', '').lower()
            if any(term in content for term in ['encrypt', 'decrypt', 'hash', 'crypto', 'ssl', 'tls']):
                encryption_usage.append(f"Encryption usage in {file_detail['filename']}")
        
        return encryption_usage or ["No encryption usage detected"]
    
    def _categorize_hardcoded_values(self, values: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize hardcoded values"""
        categories = {}
        for value in values:
            value_type = value['type']
            categories[value_type] = categories.get(value_type, 0) + 1
        return categories
    
    def _assess_hardcoded_risks(self, values: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Assess risks of hardcoded values"""
        risks = {'High': [], 'Medium': [], 'Low': []}
        for value in values:
            risk_level = value.get('risk_level', 'Medium')
            risks[risk_level].append(f"{value['type']} in {value['file']}")
        return risks
    
    def _suggest_hardcoded_fixes(self, values: List[Dict[str, Any]]) -> List[str]:
        """Suggest fixes for hardcoded values"""
        suggestions = []
        if any(v['type'] == 'URL' for v in values):
            suggestions.append("Move URLs to configuration files")
        if any(v['type'] == 'Email' for v in values):
            suggestions.append("Store email addresses in environment variables")
        if any(v['type'] == 'IP Address' for v in values):
            suggestions.append("Use DNS names instead of IP addresses")
        
        return suggestions or ["Consider moving hardcoded values to configuration files"]
    
    def _rank_files_by_complexity(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank files by complexity"""
        ranked = []
        for file_detail in files:
            complexity_score = len(file_detail['functions']) * 2 + len(file_detail['classes']) * 3 + file_detail['lines'] / 100
            ranked.append({
                'filename': file_detail['filename'],
                'complexity_score': round(complexity_score, 1),
                'functions': len(file_detail['functions']),
                'classes': len(file_detail['classes']),
                'lines': file_detail['lines']
            })
        
        return sorted(ranked, key=lambda x: x['complexity_score'], reverse=True)[:10]
    
    def _analyze_file_sizes(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze file sizes"""
        sizes = [f['lines'] for f in files]
        return {
            'average_size': round(sum(sizes) / len(sizes), 1) if sizes else 0,
            'largest_file': max(files, key=lambda x: x['lines']) if files else None,
            'smallest_file': min(files, key=lambda x: x['lines']) if files else None,
            'files_over_200_lines': [f for f in files if f['lines'] > 200]
        }
    
    def _analyze_file_responsibilities(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze file responsibilities"""
        responsibilities = []
        for file_detail in files:
            responsibility = "General purpose"
            filename = file_detail['filename'].lower()
            
            if 'test' in filename:
                responsibility = "Testing"
            elif 'config' in filename or 'setting' in filename:
                responsibility = "Configuration"
            elif 'model' in filename or 'entity' in filename:
                responsibility = "Data modeling"
            elif 'controller' in filename or 'handler' in filename:
                responsibility = "Request handling"
            elif 'service' in filename:
                responsibility = "Business logic"
            elif 'util' in filename or 'helper' in filename:
                responsibility = "Utility functions"
            
            responsibilities.append({
                'filename': file_detail['filename'],
                'responsibility': responsibility,
                'functions': len(file_detail['functions']),
                'classes': len(file_detail['classes'])
            })
        
        return responsibilities
    
    def _generate_priority_actions(self, data: Dict[str, Any]) -> List[str]:
        """Generate priority actions"""
        actions = []
        
        if len(data['security_issues']) > 0:
            actions.append("Address security vulnerabilities immediately")
        
        avg_file_size = data['total_lines'] / max(1, data['total_files'])
        if avg_file_size > 200:
            actions.append("Break down large files into smaller modules")
        
        if len(data['hardcoded_values']) > 5:
            actions.append("Move hardcoded values to configuration")
        
        return actions or ["Continue regular code maintenance"]
    
    def _generate_code_improvements(self, data: Dict[str, Any]) -> List[str]:
        """Generate code improvement suggestions"""
        improvements = []
        
        if len(data['functions']) / max(1, data['total_files']) > 10:
            improvements.append("Consider organizing functions into classes")
        
        if not any('test' in f['filename'].lower() for f in data['file_details']):
            improvements.append("Add unit tests to improve code reliability")
        
        if not any('readme' in f['filename'].lower() for f in data['file_details']):
            improvements.append("Add README documentation for the project")
        
        return improvements or ["Code structure looks good"]
    
    def _generate_architecture_suggestions(self, data: Dict[str, Any]) -> List[str]:
        """Generate architecture suggestions"""
        suggestions = []
        
        if len(data['dependencies']) > 20:
            suggestions.append("Review and minimize external dependencies")
        
        if not any('config' in f['filename'].lower() for f in data['file_details']):
            suggestions.append("Add configuration management")
        
        return suggestions or ["Architecture appears well-structured"]
    
    def _generate_security_actions(self, data: Dict[str, Any]) -> List[str]:
        """Generate security action items"""
        actions = []
        
        high_risk_issues = [issue for issue in data['security_issues'] if issue.get('severity') == 'High']
        if high_risk_issues:
            actions.append(f"Address {len(high_risk_issues)} high-risk security issues")
        
        if not any('auth' in f['filename'].lower() for f in data['file_details']):
            actions.append("Consider implementing authentication if needed")
        
        return actions or ["No immediate security actions required"]
    
    def _generate_maintenance_tasks(self, data: Dict[str, Any]) -> List[str]:
        """Generate maintenance tasks"""
        tasks = []
        
        if len(data['functions']) > 50:
            tasks.append("Review and document function purposes")
        
        if data['total_lines'] > 5000:
            tasks.append("Consider code review and refactoring opportunities")
        
        return tasks or ["Regular code review and updates"]
    
    def generate_summary_docx(self, analysis) -> Document:
        doc = Document()

        for section in doc.sections:
            section.top_margin = Cm(1.5)
            section.bottom_margin = Cm(1.5)
            section.left_margin = Cm(2)
            section.right_margin = Cm(2)

        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(10)
        paragraph_format = style.paragraph_format
        paragraph_format.space_after = Pt(4)
        paragraph_format.space_before = Pt(2)

        title = doc.add_heading(f'Executive Summary: {analysis.name}', level=0)
        title.runs[0].font.size = Pt(18)

        date_para = doc.add_paragraph()
        date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        date_run = date_para.add_run(f'Generated: {datetime.now().strftime("%B %d, %Y")}')
        date_run.font.size = Pt(8)
        date_run.font.color.rgb = RGBColor(128, 128, 128)

        doc_data = self._extract_comprehensive_data(analysis)

        ai_insights = analysis.ai_insights or {}
        comprehensive = {}
        if isinstance(ai_insights, dict):
            comp_raw = ai_insights.get('comprehensive_analysis', {})
            if isinstance(comp_raw, dict):
                comprehensive = comp_raw.get('comprehensive_analysis', comp_raw)

        file_analyses = {}
        if isinstance(ai_insights, dict):
            file_analyses = ai_insights.get('file_analyses', {})

        summary_result = analysis.analysis_results or {}
        summary_stats = summary_result.get('_summary', {})

        self._add_summary_overview(doc, analysis, doc_data, comprehensive, file_analyses, summary_stats)

        self._add_summary_risk_rag(doc, doc_data, comprehensive)

        self._add_summary_architecture(doc, doc_data, comprehensive)

        self._add_summary_quality(doc, doc_data, comprehensive)

        self._add_summary_findings(doc, doc_data, comprehensive)

        self._add_summary_team_skills(doc, comprehensive)

        self._add_summary_recommendations(doc, doc_data, comprehensive)

        return doc

    def _add_summary_overview(self, doc, analysis, doc_data, comprehensive, file_analyses, summary_stats):
        doc.add_heading('Project Overview', level=1).runs[0].font.size = Pt(14)

        total_files = doc_data.get('total_files', 0)
        total_lines = doc_data.get('total_lines', 0)
        languages = doc_data.get('languages', [])
        num_functions = len(doc_data.get('functions', []))
        num_classes = len(doc_data.get('classes', []))
        num_deps = len(doc_data.get('dependencies', []))
        num_apis = len(doc_data.get('apis', []))

        lang_str = ', '.join(languages) if languages else 'unknown technologies'

        project_type = comprehensive.get('project_type', '').replace('_', ' ')
        maturity = comprehensive.get('maturity_level', '').replace('_', ' ')
        arch_assessment = comprehensive.get('architecture_assessment', '')

        file_summaries = []
        for fname, fdata in file_analyses.items():
            if isinstance(fdata, dict):
                s = fdata.get('summary', {})
                if isinstance(s, dict) and s.get('summary'):
                    file_summaries.append(s['summary'])

        purpose_sentences = []
        for s in file_summaries[:5]:
            clean = s.strip().rstrip('.')
            if len(clean) > 20 and 'code file' not in clean.lower():
                purpose_sentences.append(clean)

        if project_type:
            intro = f'This {project_type} is built using {lang_str}'
        else:
            intro = f'This application is built using {lang_str}'

        if maturity:
            intro += f' and is currently at a {maturity} stage'
        intro += '.'

        scale = f'The codebase consists of {total_files} files totaling approximately {total_lines:,} lines of code'
        if num_functions or num_classes:
            components = []
            if num_functions:
                components.append(f'{num_functions} functions')
            if num_classes:
                components.append(f'{num_classes} classes')
            scale += f', containing {" and ".join(components)}'
        scale += '.'

        if num_deps:
            scale += f' It relies on {num_deps} external dependencies'
        if num_apis:
            scale += f' and exposes {num_apis} API endpoints'
        if num_deps or num_apis:
            scale += '.'

        overview_text = intro + ' ' + scale

        if purpose_sentences:
            purpose_text = ' Key capabilities include: ' + '; '.join(purpose_sentences[:3]) + '.'
            overview_text += purpose_text

        if arch_assessment:
            overview_text += ' ' + arch_assessment.strip().rstrip('.') + '.'

        para = doc.add_paragraph()
        run = para.add_run(overview_text)
        run.font.size = Pt(10)

        if analysis.source_type == 'github' and analysis.source_url:
            source_para = doc.add_paragraph()
            source_run = source_para.add_run(f'Source: {analysis.source_url}')
            source_run.font.size = Pt(9)
            source_run.font.color.rgb = RGBColor(100, 100, 100)

    def _add_summary_risk_rag(self, doc, doc_data, comprehensive):
        doc.add_heading('Risk Summary', level=1).runs[0].font.size = Pt(14)

        security_issues = doc_data.get('security_issues', [])
        high_security = sum(1 for i in security_issues if i.get('severity') == 'High')

        risk = comprehensive.get('risk_assessment', {})
        if not isinstance(risk, dict):
            risk = {}
        tech_debt = risk.get('technical_debt', 'unknown')
        perf_risks = risk.get('performance_risks', [])
        security_risks = risk.get('security_risks', [])

        if high_security > 0 or len(security_risks) > 3:
            sec_status = 'RED'
            sec_label = 'High Risk'
        elif len(security_issues) > 0 or len(security_risks) > 0:
            sec_status = 'AMBER'
            sec_label = 'Moderate Risk'
        else:
            sec_status = 'GREEN'
            sec_label = 'Low Risk'

        debt_str = str(tech_debt).lower()
        if debt_str in ('high', 'critical'):
            debt_status = 'RED'
            debt_label = 'High'
        elif debt_str in ('medium', 'moderate'):
            debt_status = 'AMBER'
            debt_label = 'Moderate'
        elif debt_str in ('low', 'minimal', 'none'):
            debt_status = 'GREEN'
            debt_label = 'Low'
        else:
            try:
                quality_stats = self._calculate_quality_stats(doc_data)
                score = quality_stats.get('overall_score', 50)
            except Exception:
                score = 50
            if score >= 70:
                debt_status = 'GREEN'
                debt_label = 'Low'
            elif score >= 40:
                debt_status = 'AMBER'
                debt_label = 'Moderate'
            else:
                debt_status = 'RED'
                debt_label = 'High'

        if len(perf_risks) > 3:
            perf_status = 'RED'
            perf_label = 'High Risk'
        elif len(perf_risks) > 0:
            perf_status = 'AMBER'
            perf_label = 'Moderate Risk'
        else:
            perf_status = 'GREEN'
            perf_label = 'Low Risk'

        status_colors = {
            'RED': RGBColor(220, 53, 69),
            'AMBER': RGBColor(255, 165, 0),
            'GREEN': RGBColor(40, 167, 69),
        }

        table = doc.add_table(rows=1, cols=3)
        table.style = 'Light Grid Accent 1'
        hdr = table.rows[0].cells
        hdr[0].text = 'Area'
        hdr[1].text = 'Status'
        hdr[2].text = 'Details'

        rag_items = [
            ('Security', sec_status, sec_label, f'{len(security_issues)} issues found' if security_issues else 'No issues detected'),
            ('Technical Debt', debt_status, debt_label, str(tech_debt).capitalize() if tech_debt and tech_debt != 'unknown' else debt_label),
            ('Performance', perf_status, perf_label, f'{len(perf_risks)} risks identified' if perf_risks else 'No risks identified'),
        ]

        for area, status, label, details in rag_items:
            row = table.add_row().cells
            row[0].text = area
            row[1].text = f'{label}'
            row[2].text = details
            for paragraph in row[1].paragraphs:
                for run in paragraph.runs:
                    run.font.color.rgb = status_colors.get(status, RGBColor(0, 0, 0))
                    run.bold = True

        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(9)

    def _add_summary_architecture(self, doc, doc_data, comprehensive):
        doc.add_heading('Architecture & Structure', level=1).runs[0].font.size = Pt(14)

        try:
            arch_pattern = self._detect_architectural_pattern(doc_data)
        except Exception:
            arch_pattern = 'Unknown'
        try:
            layers = self._analyze_layers(doc_data)
        except Exception:
            layers = []
        try:
            entry_points = self._identify_entry_points(doc_data)
        except Exception:
            entry_points = []

        tech_stack = comprehensive.get('technology_stack', [])

        if arch_pattern:
            para = doc.add_paragraph()
            para.add_run('Architecture Pattern: ').bold = True
            para.add_run(arch_pattern)

        if tech_stack:
            para = doc.add_paragraph()
            para.add_run('Technology Stack: ').bold = True
            para.add_run(', '.join(tech_stack[:10]) if isinstance(tech_stack, list) else str(tech_stack))

        if layers and layers != ['Single-layer structure']:
            para = doc.add_paragraph()
            para.add_run('Application Layers:').bold = True
            for layer in layers:
                doc.add_paragraph(layer, style='List Bullet')

        if entry_points:
            para = doc.add_paragraph()
            para.add_run('Entry Points: ').bold = True
            para.add_run(', '.join(entry_points[:5]))

        lang_breakdown = self._get_language_breakdown(doc_data)
        if lang_breakdown:
            para = doc.add_paragraph()
            para.add_run('Language Distribution:').bold = True
            for lang, lines in sorted(lang_breakdown.items(), key=lambda x: x[1], reverse=True):
                pct = round(lines / max(doc_data.get('total_lines', 1), 1) * 100)
                doc.add_paragraph(f'{lang}: {lines:,} lines ({pct}%)', style='List Bullet')

        dependencies = doc_data.get('dependencies', [])
        if dependencies:
            external = [d for d in dependencies if not d.startswith('.')]
            internal = [d for d in dependencies if d.startswith('.')]
            para = doc.add_paragraph()
            para.add_run('Dependency Health: ').bold = True
            dep_text = f'{len(dependencies)} total dependencies ({len(external)} external, {len(internal)} internal).'
            if len(external) > 15:
                dep_text += ' The project has a high reliance on third-party libraries, which increases supply-chain risk. Consider auditing and minimizing external dependencies.'
            elif len(external) > 8:
                dep_text += ' Moderate use of external libraries. Consider periodic review of dependency health and updates.'
            else:
                dep_text += ' Healthy dependency footprint with limited external reliance.'
            para.add_run(dep_text)

        file_details = doc_data.get('file_details', [])
        total_lines = doc_data.get('total_lines', 0)
        total_files = doc_data.get('total_files', 0)
        if file_details and total_files > 0:
            avg_size = round(total_lines / total_files)
            largest = max(file_details, key=lambda x: x.get('lines', 0))
            para = doc.add_paragraph()
            para.add_run('Codebase Size Profile: ').bold = True
            size_text = f'Average file size is {avg_size} lines.'
            size_text += f' The largest file is {largest.get("filename", "unknown")} at {largest.get("lines", 0):,} lines.'
            large_files = [f for f in file_details if f.get('lines', 0) > 300]
            if large_files:
                size_text += f' {len(large_files)} file(s) exceed 300 lines and may benefit from being split into smaller modules.'
            else:
                size_text += ' All files are reasonably sized, indicating good code organization.'
            para.add_run(size_text)

    def _add_summary_quality(self, doc, doc_data, comprehensive):
        doc.add_heading('Code Quality Snapshot', level=1).runs[0].font.size = Pt(14)

        try:
            quality_stats = self._calculate_quality_stats(doc_data)
        except Exception:
            quality_stats = {'overall_score': 0, 'avg_complexity': 0, 'maintainability': 0}

        maintainability = comprehensive.get('maintainability_score', '')
        tech_debt = ''
        risk = comprehensive.get('risk_assessment', {})
        if isinstance(risk, dict):
            tech_debt = risk.get('technical_debt', '')

        score = quality_stats.get('overall_score', 0)
        complexity = quality_stats.get('avg_complexity', 0)
        maint = quality_stats.get('maintainability', 0)

        table = doc.add_table(rows=1, cols=3)
        table.style = 'Light Grid Accent 1'
        hdr = table.rows[0].cells
        hdr[0].text = 'Metric'
        hdr[1].text = 'Score'
        hdr[2].text = 'Assessment'

        metrics = [
            ('Overall Quality', f'{score}/100', 'Good' if score >= 70 else 'Needs Improvement' if score >= 40 else 'Poor'),
            ('Code Complexity', f'{complexity}', 'Low' if complexity <= 3 else 'Medium' if complexity <= 7 else 'High'),
            ('Maintainability', f'{maint}/100', 'Good' if maint >= 70 else 'Fair' if maint >= 40 else 'Poor'),
        ]

        if maintainability:
            metrics.append(('AI Maintainability Rating', str(maintainability), ''))
        if tech_debt:
            metrics.append(('Technical Debt', str(tech_debt).title(), ''))

        file_details = doc_data.get('file_details', [])
        has_tests = any('test' in f.get('filename', '').lower() for f in file_details)
        test_label = 'Detected' if has_tests else 'Not Detected'
        test_assessment = 'Test files present in codebase' if has_tests else 'No test files found — consider adding tests'
        metrics.append(('Test Coverage', test_label, test_assessment))

        for metric, score_val, assessment in metrics:
            row = table.add_row().cells
            row[0].text = metric
            row[1].text = score_val
            row[2].text = assessment

        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(9)

        tech_debt_val = comprehensive.get('risk_assessment', {})
        if isinstance(tech_debt_val, dict):
            td = tech_debt_val.get('technical_debt', '')
        else:
            td = ''
        if td and str(td).lower() not in ('unknown', ''):
            para = doc.add_paragraph()
            para.add_run('Technical Debt Assessment: ').bold = True
            td_str = str(td).lower()
            if td_str in ('high', 'critical'):
                para.add_run(f'Technical debt is rated as {td_str}. This means the codebase may require significant refactoring effort before new features can be added efficiently. Budget additional time for cleanup and modernization.')
            elif td_str in ('medium', 'moderate'):
                para.add_run(f'Technical debt is at a {td_str} level. Some areas of the code would benefit from refactoring, but the codebase is still manageable. Address high-impact debt items during regular development cycles.')
            else:
                para.add_run(f'Technical debt is {td_str}. The codebase is in good shape and new features can be added without significant overhead.')

    def _add_summary_findings(self, doc, doc_data, comprehensive):
        doc.add_heading('Key Findings', level=1).runs[0].font.size = Pt(14)

        security_issues = doc_data.get('security_issues', [])
        hardcoded = doc_data.get('hardcoded_values', [])

        risk = comprehensive.get('risk_assessment', {})
        security_risks = []
        perf_risks = []
        if isinstance(risk, dict):
            security_risks = risk.get('security_risks', [])
            perf_risks = risk.get('performance_risks', [])

        try:
            core_modules = self._identify_core_modules(doc_data)
        except Exception:
            core_modules = []
        if core_modules:
            para = doc.add_paragraph()
            para.add_run('Core Components: ').bold = True
            module_names = [m['name'] for m in core_modules[:5]]
            para.add_run(', '.join(module_names))

        try:
            important_classes = self._get_important_classes(doc_data)
        except Exception:
            important_classes = []
        if important_classes:
            para = doc.add_paragraph()
            para.add_run('Key Classes: ').bold = True
            class_names = [c['name'] for c in important_classes[:5]]
            para.add_run(', '.join(class_names))

        if security_issues:
            high_count = sum(1 for i in security_issues if i.get('severity') == 'High')
            med_count = sum(1 for i in security_issues if i.get('severity') == 'Medium')
            para = doc.add_paragraph()
            para.add_run('Security: ').bold = True
            parts = []
            if high_count:
                parts.append(f'{high_count} high-risk issues')
            if med_count:
                parts.append(f'{med_count} medium-risk issues')
            para.add_run(', '.join(parts) + ' detected.')
        elif security_risks:
            para = doc.add_paragraph()
            para.add_run('Security Risks: ').bold = True
            for r in security_risks[:3]:
                doc.add_paragraph(str(r), style='List Bullet')
        else:
            para = doc.add_paragraph()
            para.add_run('Security: ').bold = True
            para.add_run('No significant security concerns detected.')

        if hardcoded:
            para = doc.add_paragraph()
            para.add_run('Hardcoded Values: ').bold = True
            para.add_run(f'{len(hardcoded)} hardcoded values found that should be moved to configuration.')

        if perf_risks:
            para = doc.add_paragraph()
            para.add_run('Performance Considerations: ').bold = True
            for r in perf_risks[:3]:
                doc.add_paragraph(str(r), style='List Bullet')

        apis = doc_data.get('apis', [])
        if apis:
            para = doc.add_paragraph()
            para.add_run('API Surface: ').bold = True
            para.add_run(f'{len(apis)} API endpoint(s) detected.')
            endpoint_names = []
            for api in apis[:8]:
                if isinstance(api, dict):
                    name = api.get('endpoint', api.get('name', api.get('path', '')))
                    method = api.get('method', '')
                    if name:
                        endpoint_names.append(f'{method} {name}'.strip() if method else str(name))
                elif isinstance(api, str):
                    endpoint_names.append(api)
            if endpoint_names:
                for ep in endpoint_names:
                    doc.add_paragraph(ep, style='List Bullet')
                if len(apis) > 8:
                    doc.add_paragraph(f'...and {len(apis) - 8} more endpoints', style='List Bullet')

    def _add_summary_team_skills(self, doc, comprehensive):
        team_recs = comprehensive.get('team_recommendations', {})
        if not isinstance(team_recs, dict):
            team_recs = {}

        skills = team_recs.get('skill_requirements', [])
        gaps = team_recs.get('knowledge_gaps', [])
        practices = team_recs.get('development_practices', [])

        if not skills and not gaps and not practices:
            return

        doc.add_heading('Team & Skills Assessment', level=1).runs[0].font.size = Pt(14)

        if skills and isinstance(skills, list):
            para = doc.add_paragraph()
            para.add_run('Required Skills: ').bold = True
            para.add_run(', '.join(str(s) for s in skills[:8]))

        if gaps and isinstance(gaps, list):
            para = doc.add_paragraph()
            para.add_run('Knowledge Gaps: ').bold = True
            para.add_run('The following areas may need additional training or hiring:')
            for gap in gaps[:5]:
                doc.add_paragraph(str(gap), style='List Bullet')

        if practices and isinstance(practices, list):
            para = doc.add_paragraph()
            para.add_run('Recommended Practices: ').bold = True
            for practice in practices[:5]:
                doc.add_paragraph(str(practice), style='List Bullet')

    def _add_summary_recommendations(self, doc, doc_data, comprehensive):
        doc.add_heading('Recommendations', level=1).runs[0].font.size = Pt(14)

        priority_actions = self._generate_priority_actions(doc_data)
        code_improvements = self._generate_code_improvements(doc_data)
        arch_suggestions = self._generate_architecture_suggestions(doc_data)

        modernization = comprehensive.get('modernization_opportunities', [])
        team_recs = comprehensive.get('team_recommendations', {})
        scalability = comprehensive.get('scalability_considerations', [])

        all_recs = []

        for action in priority_actions:
            if action != 'Continue regular code maintenance':
                all_recs.append(('High Priority', action))

        for imp in code_improvements:
            if imp != 'Code structure looks good':
                all_recs.append(('Code Quality', imp))

        for sug in arch_suggestions:
            if sug != 'Architecture appears well-structured':
                all_recs.append(('Architecture', sug))

        if isinstance(modernization, list):
            for m in modernization[:3]:
                all_recs.append(('Modernization', str(m)))

        if isinstance(scalability, list):
            for s in scalability[:2]:
                all_recs.append(('Scalability', str(s)))

        if isinstance(team_recs, dict):
            for practice in team_recs.get('development_practices', [])[:2]:
                all_recs.append(('Best Practices', str(practice)))

        if all_recs:
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Light Grid Accent 1'
            hdr = table.rows[0].cells
            hdr[0].text = 'Category'
            hdr[1].text = 'Recommendation'

            for category, rec in all_recs[:10]:
                row = table.add_row().cells
                row[0].text = category
                row[1].text = rec

            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(9)
        else:
            doc.add_paragraph('The codebase is in good shape. Continue with regular maintenance and code reviews.')

        footer_para = doc.add_paragraph()
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer_run = footer_para.add_run(f'\n--- End of Executive Summary ---')
        footer_run.font.size = Pt(8)
        footer_run.font.color.rgb = RGBColor(150, 150, 150)

    def generate_docx(self, documentation_data: Dict[str, Any]) -> Document:
        """Generate DOCX document from documentation data"""
        doc = Document()
        
        # Add title
        title = doc.add_heading(f"Code Analysis Report: {documentation_data['metadata']['analysis_name']}", 0)
        
        # Add metadata
        doc.add_paragraph(f"Generated: {documentation_data['metadata']['generated_at']}")
        doc.add_paragraph(f"Total Files: {documentation_data['metadata']['total_files']}")
        doc.add_paragraph(f"Languages: {', '.join(documentation_data['metadata']['languages'])}")
        doc.add_paragraph(f"Total Lines: {documentation_data['metadata']['total_lines']}")
        
        # Add sections
        for section_key, section_data in documentation_data['sections'].items():
            if section_data and section_data.get('content'):
                # Add section heading
                doc.add_heading(section_data['title'], level=1)
                
                # Add section content based on structure
                self._add_section_to_docx(doc, section_data['content'])
                
                # Add page break after each major section
                doc.add_page_break()
        
        return doc
    
    def _add_section_to_docx(self, doc: Document, content: Dict[str, Any]):
        """Add section content to DOCX document"""
        
        for key, value in content.items():
            if key == 'summary' and isinstance(value, str):
                doc.add_paragraph(value)
            elif key == 'statistics' and isinstance(value, dict):
                doc.add_heading('Statistics', level=2)
                for stat_key, stat_value in value.items():
                    doc.add_paragraph(f"{stat_key.replace('_', ' ').title()}: {stat_value}")
            elif isinstance(value, list) and value:
                doc.add_heading(key.replace('_', ' ').title(), level=2)
                for item in value[:10]:  # Limit to 10 items
                    if isinstance(item, dict):
                        item_text = ', '.join([f"{k}: {v}" for k, v in item.items() if isinstance(v, (str, int, float))])
                        doc.add_paragraph(f"• {item_text}")
                    else:
                        doc.add_paragraph(f"• {str(item)}")
            elif isinstance(value, dict):
                doc.add_heading(key.replace('_', ' ').title(), level=2)
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, (str, int, float)):
                        doc.add_paragraph(f"{sub_key.replace('_', ' ').title()}: {sub_value}")
                    elif isinstance(sub_value, list) and sub_value:
                        doc.add_paragraph(f"{sub_key.replace('_', ' ').title()}:")
                        for item in sub_value[:5]:  # Limit to 5 items
                            doc.add_paragraph(f"  • {str(item)}")
            elif isinstance(value, (str, int, float)):
                doc.add_paragraph(f"{key.replace('_', ' ').title()}: {value}")


def generate_documentation_for_analysis(analysis_id: int) -> Dict[str, Any]:
    """Generate documentation for a specific analysis"""
    from models import Analysis, db
    
    analysis = db.session.get(Analysis, analysis_id)
    if not analysis:
        return {'error': 'Analysis not found'}
    
    generator = DocumentationGenerator()
    return generator.generate_documentation(analysis)