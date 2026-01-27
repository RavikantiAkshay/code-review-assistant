#!/usr/bin/env python3
"""
Evaluation Script for Code Review Assistant

This script evaluates the Code Review Assistant by:
1. Running the review on the seed repository
2. Comparing detected issues against ground truth
3. Calculating precision, recall, and F1-score
4. Generating a detailed evaluation report
"""

import json
import os
import sys
import requests
from datetime import datetime
from typing import Dict, List, Set, Tuple
from pathlib import Path

# Configuration
API_BASE = "http://localhost:8000"
SEED_REPO_PATH = Path(__file__).parent / "seed_repo"
GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"
REPORT_PATH = Path(__file__).parent / "evaluation_report.md"


def load_ground_truth() -> Dict:
    """Load the ground truth JSON file."""
    with open(GROUND_TRUTH_PATH, "r") as f:
        return json.load(f)


def run_review_on_seed_repo() -> Dict:
    """Run the code review on the seed repository."""
    # First, we need to get the files from the seed repo
    src_path = SEED_REPO_PATH / "src"
    
    # Collect all files
    files = []
    for file in src_path.iterdir():
        if file.suffix in [".py", ".js", ".jsx"]:
            files.append(f"src/{file.name}")
    
    # Make a review request
    # Note: We need to use the absolute path for the review
    review_request = {
        "temp_dir": str(SEED_REPO_PATH.absolute()),
        "files": files,
        "ruleset": None  # Auto-detect
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/review",
            json=review_request,
            timeout=120
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling review API: {e}")
        return {"ranked_issues": [], "file_results": [], "summary": {}}


def normalize_issue(issue: Dict) -> Tuple[str, int, str, str]:
    """Normalize an issue to a comparable tuple (file, line, category, severity)."""
    file = issue.get("file", "").replace("\\", "/")
    if not file.startswith("src/"):
        file = f"src/{file}" if "/" not in file else file
    
    line = issue.get("line", 0)
    category = issue.get("category", "unknown").lower()
    severity = issue.get("severity", "low").lower()
    
    return (file, line, category, severity)


def match_issues(detected: List[Dict], ground_truth_issues: List[Dict], line_tolerance: int = 5) -> Dict:
    """
    Match detected issues against ground truth.
    
    Returns:
        Dict with true_positives, false_positives, false_negatives
    """
    true_positives = []
    false_positives = []
    matched_gt_ids = set()
    
    for det in detected:
        det_file = det.get("file", "").replace("\\", "/")
        det_line = det.get("line", 0)
        det_category = det.get("category", "").lower()
        det_severity = det.get("severity", "").lower()
        
        best_match = None
        best_match_score = 0
        
        for gt in ground_truth_issues:
            if gt["id"] in matched_gt_ids:
                continue
            
            gt_file = gt.get("file", "")
            gt_line = gt.get("line", 0)
            gt_category = gt.get("category", "").lower()
            gt_severity = gt.get("severity", "").lower()
            
            # Check file match
            if gt_file not in det_file and det_file not in gt_file:
                continue
            
            # Check line proximity
            line_diff = abs(det_line - gt_line)
            if line_diff > line_tolerance:
                continue
            
            # Calculate match score
            score = 0
            if gt_category == det_category:
                score += 2
            if gt_severity == det_severity:
                score += 1
            score += (line_tolerance - line_diff) / line_tolerance
            
            if score > best_match_score:
                best_match_score = score
                best_match = gt
        
        if best_match:
            true_positives.append({
                "detected": det,
                "ground_truth": best_match,
                "match_score": best_match_score
            })
            matched_gt_ids.add(best_match["id"])
        else:
            false_positives.append(det)
    
    # Find false negatives (ground truth issues not matched)
    false_negatives = [gt for gt in ground_truth_issues if gt["id"] not in matched_gt_ids]
    
    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives
    }


def calculate_metrics(match_results: Dict) -> Dict:
    """Calculate precision, recall, and F1-score."""
    tp = len(match_results["true_positives"])
    fp = len(match_results["false_positives"])
    fn = len(match_results["false_negatives"])
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1_score": f1
    }


def calculate_metrics_by_category(match_results: Dict, ground_truth: Dict) -> Dict:
    """Calculate metrics broken down by category."""
    categories = ["security", "correctness", "complexity", "readability"]
    results = {}
    
    for category in categories:
        tp = len([m for m in match_results["true_positives"] 
                  if m["ground_truth"].get("category", "").lower() == category])
        fp = len([d for d in match_results["false_positives"] 
                  if d.get("category", "").lower() == category])
        fn = len([gt for gt in match_results["false_negatives"] 
                  if gt.get("category", "").lower() == category])
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        results[category] = {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1
        }
    
    return results


def calculate_metrics_by_severity(match_results: Dict) -> Dict:
    """Calculate metrics broken down by severity."""
    severities = ["high", "medium", "low"]
    results = {}
    
    for severity in severities:
        tp = len([m for m in match_results["true_positives"] 
                  if m["ground_truth"].get("severity", "").lower() == severity])
        fp = len([d for d in match_results["false_positives"] 
                  if d.get("severity", "").lower() == severity])
        fn = len([gt for gt in match_results["false_negatives"] 
                  if gt.get("severity", "").lower() == severity])
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        results[severity] = {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1
        }
    
    return results


def generate_report(
    ground_truth: Dict,
    review_results: Dict,
    match_results: Dict,
    overall_metrics: Dict,
    category_metrics: Dict,
    severity_metrics: Dict
) -> str:
    """Generate a markdown evaluation report."""
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""# Code Review Assistant - Evaluation Report

**Generated:** {timestamp}

## Executive Summary

| Metric | Value |
|--------|-------|
| **Total Ground Truth Issues** | {ground_truth["total_issues"]} |
| **Total Detected Issues** | {len(review_results.get("ranked_issues", []))} |
| **True Positives** | {overall_metrics["true_positives"]} |
| **False Positives** | {overall_metrics["false_positives"]} |
| **False Negatives** | {overall_metrics["false_negatives"]} |

## Overall Performance

| Metric | Score |
|--------|-------|
| **Precision** | {overall_metrics["precision"]:.2%} |
| **Recall** | {overall_metrics["recall"]:.2%} |
| **F1-Score** | {overall_metrics["f1_score"]:.2%} |

## Performance by Category

| Category | Precision | Recall | F1-Score | TP | FP | FN |
|----------|-----------|--------|----------|----|----|-----|
"""
    
    for category, metrics in category_metrics.items():
        report += f"| {category.capitalize()} | {metrics['precision']:.2%} | {metrics['recall']:.2%} | {metrics['f1_score']:.2%} | {metrics['true_positives']} | {metrics['false_positives']} | {metrics['false_negatives']} |\n"
    
    report += """
## Performance by Severity

| Severity | Precision | Recall | F1-Score | TP | FP | FN |
|----------|-----------|--------|----------|----|----|-----|
"""
    
    for severity, metrics in severity_metrics.items():
        report += f"| {severity.capitalize()} | {metrics['precision']:.2%} | {metrics['recall']:.2%} | {metrics['f1_score']:.2%} | {metrics['true_positives']} | {metrics['false_positives']} | {metrics['false_negatives']} |\n"
    
    report += """
## Detailed Analysis

### Successfully Detected Issues (True Positives)

"""
    
    if match_results["true_positives"]:
        for i, tp in enumerate(match_results["true_positives"][:10], 1):
            gt = tp["ground_truth"]
            det = tp["detected"]
            report += f"{i}. **{gt['id']}** ({gt['file']}:{gt['line']}) - {gt['type']}\n"
            report += f"   - Ground Truth: {gt['message']}\n"
            report += f"   - Detected: {det.get('message', 'N/A')[:100]}\n\n"
        
        if len(match_results["true_positives"]) > 10:
            report += f"*...and {len(match_results['true_positives']) - 10} more*\n\n"
    else:
        report += "*No true positives detected*\n\n"
    
    report += """### Missed Issues (False Negatives)

"""
    
    if match_results["false_negatives"]:
        for i, fn in enumerate(match_results["false_negatives"][:10], 1):
            report += f"{i}. **{fn['id']}** ({fn['file']}:{fn['line']}) - {fn['type']}\n"
            report += f"   - Severity: {fn['severity']}, Category: {fn['category']}\n"
            report += f"   - Message: {fn['message']}\n\n"
        
        if len(match_results["false_negatives"]) > 10:
            report += f"*...and {len(match_results['false_negatives']) - 10} more*\n\n"
    else:
        report += "*All ground truth issues were detected!*\n\n"
    
    report += """### Extra Detections (False Positives)

"""
    
    if match_results["false_positives"]:
        for i, fp in enumerate(match_results["false_positives"][:10], 1):
            report += f"{i}. {fp.get('file', 'N/A')}:{fp.get('line', 'N/A')} - {fp.get('category', 'N/A')}\n"
            report += f"   - Severity: {fp.get('severity', 'N/A')}\n"
            report += f"   - Message: {fp.get('message', 'N/A')[:100]}\n\n"
        
        if len(match_results["false_positives"]) > 10:
            report += f"*...and {len(match_results['false_positives']) - 10} more*\n\n"
    else:
        report += "*No false positives - all detections matched ground truth!*\n\n"
    
    report += """## Recommendations

Based on the evaluation results:

"""
    
    # Add recommendations based on metrics
    if overall_metrics["precision"] < 0.7:
        report += "- **Improve Precision**: High false positive rate. Consider stricter detection thresholds.\n"
    if overall_metrics["recall"] < 0.7:
        report += "- **Improve Recall**: Missing many issues. Consider expanding detection patterns.\n"
    
    # Check category performance
    for category, metrics in category_metrics.items():
        if metrics["recall"] < 0.5:
            report += f"- **{category.capitalize()}**: Low recall ({metrics['recall']:.0%}). Add more rules for this category.\n"
    
    report += """
---
*Report generated by Code Review Assistant Evaluation System*
"""
    
    return report


def flatten_ground_truth_issues(ground_truth: Dict) -> List[Dict]:
    """Flatten all issues from ground truth into a single list."""
    all_issues = []
    for file_path, file_data in ground_truth["files"].items():
        for issue in file_data["issues"]:
            issue_copy = issue.copy()
            issue_copy["file"] = file_path
            all_issues.append(issue_copy)
    return all_issues


def main():
    """Main evaluation function."""
    print("=" * 60)
    print("Code Review Assistant - Evaluation")
    print("=" * 60)
    
    # Load ground truth
    print("\n1. Loading ground truth...")
    ground_truth = load_ground_truth()
    gt_issues = flatten_ground_truth_issues(ground_truth)
    print(f"   Loaded {len(gt_issues)} ground truth issues")
    
    # Run review
    print("\n2. Running code review on seed repository...")
    review_results = run_review_on_seed_repo()
    detected_issues = review_results.get("ranked_issues", [])
    print(f"   Detected {len(detected_issues)} issues")
    
    # Match issues
    print("\n3. Matching detected issues against ground truth...")
    match_results = match_issues(detected_issues, gt_issues)
    print(f"   True Positives: {len(match_results['true_positives'])}")
    print(f"   False Positives: {len(match_results['false_positives'])}")
    print(f"   False Negatives: {len(match_results['false_negatives'])}")
    
    # Calculate metrics
    print("\n4. Calculating metrics...")
    overall_metrics = calculate_metrics(match_results)
    category_metrics = calculate_metrics_by_category(match_results, ground_truth)
    severity_metrics = calculate_metrics_by_severity(match_results)
    
    print(f"\n   Overall Performance:")
    print(f"   - Precision: {overall_metrics['precision']:.2%}")
    print(f"   - Recall:    {overall_metrics['recall']:.2%}")
    print(f"   - F1-Score:  {overall_metrics['f1_score']:.2%}")
    
    # Generate report
    print("\n5. Generating evaluation report...")
    report = generate_report(
        ground_truth,
        review_results,
        match_results,
        overall_metrics,
        category_metrics,
        severity_metrics
    )
    
    with open(REPORT_PATH, "w") as f:
        f.write(report)
    print(f"   Report saved to: {REPORT_PATH}")
    
    # Also save raw results as JSON
    results_json_path = Path(__file__).parent / "evaluation_results.json"
    with open(results_json_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "overall_metrics": overall_metrics,
            "category_metrics": category_metrics,
            "severity_metrics": severity_metrics,
            "detected_count": len(detected_issues),
            "ground_truth_count": len(gt_issues)
        }, f, indent=2)
    print(f"   Results JSON saved to: {results_json_path}")
    
    print("\n" + "=" * 60)
    print("Evaluation Complete!")
    print("=" * 60)
    
    return overall_metrics


if __name__ == "__main__":
    main()
