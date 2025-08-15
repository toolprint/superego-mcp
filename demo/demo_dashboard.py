#!/usr/bin/env python3
"""
Demo Dashboard for Superego MCP.

Central navigation hub for all available demos with descriptions and quick launch.
"""

import sys
import subprocess
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add the project source directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from demo_utils import (
    Colors,
    create_demo_header,
    format_timestamp,
    prompt_yes_no
)


@dataclass
class DemoInfo:
    """Information about a demo."""
    name: str
    script: str
    description: str
    category: str
    difficulty: str  # beginner, intermediate, advanced
    estimated_time: str
    features: List[str]
    requirements: List[str] = None


class DemoDashboard:
    """Central dashboard for all Superego MCP demos."""
    
    def __init__(self):
        """Initialize the demo dashboard."""
        self.demos = self._register_demos()
        self.categories = self._get_categories()
        self.demo_dir = Path(__file__).parent
        
        # Track launched demos
        self.launch_history = []
    
    def _register_demos(self) -> List[DemoInfo]:
        """Register all available demos."""
        return [
            # Basic Demos
            DemoInfo(
                name="Claude Code Demo",
                script="claude_code_demo.py",
                description="Interactive demo showcasing Claude Code tool security evaluation",
                category="Basic",
                difficulty="beginner",
                estimated_time="5-10 minutes",
                features=[
                    "Pre-defined security scenarios",
                    "Interactive tool request builder",
                    "Real-time security decisions",
                    "Session summary and export"
                ]
            ),
            DemoInfo(
                name="Simple FastAgent Demo",
                script="simple_fastagent_demo.py",
                description="Streamlined demo with essential FastAgent patterns",
                category="Basic",
                difficulty="beginner",
                estimated_time="5 minutes",
                features=[
                    "Quick demo mode (3 scenarios)",
                    "Full demo with all scenarios",
                    "Custom scenario selection",
                    "Simple interface"
                ]
            ),
            
            # Intermediate Demos
            DemoInfo(
                name="FastAgent Demo",
                script="fastagent_demo.py",
                description="Comprehensive FastAgent integration patterns",
                category="Intermediate",
                difficulty="intermediate",
                estimated_time="10-15 minutes",
                features=[
                    "Category-based scenario organization",
                    "Risk assessment mode",
                    "Interactive category selection",
                    "Detailed security patterns"
                ]
            ),
            DemoInfo(
                name="Security Scenarios Demo",
                script="security_scenarios.py",
                description="Extensive security evaluation scenarios across risk levels",
                category="Intermediate",
                difficulty="intermediate",
                estimated_time="15-20 minutes",
                features=[
                    "40+ security scenarios",
                    "Risk matrix analysis",
                    "Scenario browser with search",
                    "Detailed security reports"
                ]
            ),
            
            # Advanced Demos
            DemoInfo(
                name="Interactive Hook Demo",
                script="interactive_hook_demo.py",
                description="Menu-driven demo with real-time feedback and templates",
                category="Advanced",
                difficulty="advanced",
                estimated_time="10-30 minutes",
                features=[
                    "Scenario templates",
                    "Custom request builder",
                    "Session statistics",
                    "Multiple export formats",
                    "Request replay"
                ]
            ),
            DemoInfo(
                name="Scenario Runner",
                script="scenario_runner.py",
                description="Batch execution with detailed metrics and reporting",
                category="Advanced",
                difficulty="advanced",
                estimated_time="20-30 minutes",
                features=[
                    "Batch scenario execution",
                    "Performance metrics",
                    "Filtered scenario runs",
                    "HTML/CSV/JSON export",
                    "Custom scenario files"
                ]
            ),
            
            # Utility Demos
            DemoInfo(
                name="Hook Simulator",
                script="hook_simulator.py",
                description="Low-level hook simulation for testing and development",
                category="Utility",
                difficulty="advanced",
                estimated_time="Variable",
                features=[
                    "Direct hook testing",
                    "Custom hook inputs",
                    "Batch simulation mode",
                    "Detailed logging"
                ],
                requirements=["Understanding of Claude Code hooks"]
            )
        ]
    
    def _get_categories(self) -> List[str]:
        """Get unique demo categories."""
        categories = set()
        for demo in self.demos:
            categories.add(demo.category)
        return sorted(list(categories))
    
    def show_welcome(self):
        """Display welcome message."""
        print(create_demo_header("Superego MCP Demo Dashboard"))
        print(f"\nWelcome to the Superego MCP Demo Suite!")
        print(f"Time: {format_timestamp()}")
        print(f"\nThis dashboard provides easy access to all available demos.")
        print(f"Total demos available: {len(self.demos)}")
    
    def show_main_menu(self):
        """Display main menu."""
        print(f"\n{Colors.BOLD}Main Menu:{Colors.RESET}")
        print("1. Browse all demos")
        print("2. Browse by category")
        print("3. Browse by difficulty")
        print("4. Quick launch (recommended demos)")
        print("5. Search demos")
        print("6. View demo details")
        print("7. Launch history")
        print("8. Help")
        print("9. Exit")
    
    def browse_all_demos(self):
        """Browse all available demos."""
        print(f"\n{Colors.BOLD}All Available Demos:{Colors.RESET}")
        
        for i, demo in enumerate(self.demos, 1):
            difficulty_color = {
                "beginner": Colors.GREEN,
                "intermediate": Colors.YELLOW,
                "advanced": Colors.RED
            }.get(demo.difficulty, Colors.RESET)
            
            print(f"\n{i}. {Colors.CYAN}{demo.name}{Colors.RESET}")
            print(f"   Category: {demo.category}")
            print(f"   Difficulty: {difficulty_color}{demo.difficulty}{Colors.RESET}")
            print(f"   Time: {demo.estimated_time}")
            print(f"   Description: {demo.description}")
        
        self._launch_prompt()
    
    def browse_by_category(self):
        """Browse demos by category."""
        print(f"\n{Colors.BOLD}Categories:{Colors.RESET}")
        
        for i, category in enumerate(self.categories, 1):
            demos_in_cat = [d for d in self.demos if d.category == category]
            print(f"{i}. {category} ({len(demos_in_cat)} demos)")
        
        choice = input("\nSelect category: ").strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(self.categories):
                category = self.categories[idx]
                self._show_category_demos(category)
        except (ValueError, IndexError):
            print(f"{Colors.RED}Invalid selection{Colors.RESET}")
    
    def _show_category_demos(self, category: str):
        """Show demos in a specific category."""
        demos = [d for d in self.demos if d.category == category]
        
        print(f"\n{Colors.BOLD}{category} Demos:{Colors.RESET}")
        
        for i, demo in enumerate(demos, 1):
            print(f"\n{i}. {Colors.CYAN}{demo.name}{Colors.RESET}")
            print(f"   {demo.description}")
        
        self._launch_prompt(demos)
    
    def browse_by_difficulty(self):
        """Browse demos by difficulty level."""
        difficulties = ["beginner", "intermediate", "advanced"]
        
        print(f"\n{Colors.BOLD}Difficulty Levels:{Colors.RESET}")
        
        for i, difficulty in enumerate(difficulties, 1):
            demos_count = len([d for d in self.demos if d.difficulty == difficulty])
            color = {
                "beginner": Colors.GREEN,
                "intermediate": Colors.YELLOW,
                "advanced": Colors.RED
            }[difficulty]
            print(f"{i}. {color}{difficulty.title()}{Colors.RESET} ({demos_count} demos)")
        
        choice = input("\nSelect difficulty: ").strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(difficulties):
                difficulty = difficulties[idx]
                demos = [d for d in self.demos if d.difficulty == difficulty]
                
                print(f"\n{Colors.BOLD}{difficulty.title()} Demos:{Colors.RESET}")
                for i, demo in enumerate(demos, 1):
                    print(f"{i}. {demo.name} - {demo.description}")
                
                self._launch_prompt(demos)
        except (ValueError, IndexError):
            print(f"{Colors.RED}Invalid selection{Colors.RESET}")
    
    def quick_launch(self):
        """Show recommended demos for quick launch."""
        recommended = [
            ("Beginner", "simple_fastagent_demo.py", "Great starting point"),
            ("Interactive", "interactive_hook_demo.py", "Best for exploration"),
            ("Comprehensive", "security_scenarios.py", "Most thorough testing")
        ]
        
        print(f"\n{Colors.BOLD}Quick Launch - Recommended Demos:{Colors.RESET}")
        
        for i, (level, script, reason) in enumerate(recommended, 1):
            demo = next((d for d in self.demos if d.script == script), None)
            if demo:
                print(f"{i}. {Colors.CYAN}{demo.name}{Colors.RESET}")
                print(f"   Recommended for: {level}")
                print(f"   Why: {reason}")
        
        choice = input("\nSelect demo to launch (1-3): ").strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(recommended):
                script = recommended[idx][1]
                demo = next((d for d in self.demos if d.script == script), None)
                if demo:
                    self._launch_demo(demo)
        except (ValueError, IndexError):
            print(f"{Colors.RED}Invalid selection{Colors.RESET}")
    
    def search_demos(self):
        """Search for demos by keyword."""
        keyword = input("\nSearch keyword: ").strip().lower()
        
        if not keyword:
            return
        
        matches = []
        for demo in self.demos:
            if (keyword in demo.name.lower() or 
                keyword in demo.description.lower() or
                keyword in demo.category.lower() or
                any(keyword in feature.lower() for feature in demo.features)):
                matches.append(demo)
        
        if matches:
            print(f"\n{Colors.BOLD}Search Results ({len(matches)} matches):{Colors.RESET}")
            for i, demo in enumerate(matches, 1):
                print(f"{i}. {Colors.CYAN}{demo.name}{Colors.RESET} - {demo.description}")
            
            self._launch_prompt(matches)
        else:
            print(f"{Colors.YELLOW}No demos found matching '{keyword}'{Colors.RESET}")
    
    def view_demo_details(self):
        """View detailed information about a specific demo."""
        print(f"\n{Colors.BOLD}Select Demo for Details:{Colors.RESET}")
        
        for i, demo in enumerate(self.demos, 1):
            print(f"{i}. {demo.name}")
        
        choice = input("\nSelect demo: ").strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(self.demos):
                self._show_demo_details(self.demos[idx])
        except (ValueError, IndexError):
            print(f"{Colors.RED}Invalid selection{Colors.RESET}")
    
    def _show_demo_details(self, demo: DemoInfo):
        """Show detailed information about a demo."""
        difficulty_color = {
            "beginner": Colors.GREEN,
            "intermediate": Colors.YELLOW,
            "advanced": Colors.RED
        }.get(demo.difficulty, Colors.RESET)
        
        print(f"\n{Colors.BOLD}Demo Details: {demo.name}{Colors.RESET}")
        print(f"\n{Colors.CYAN}Script:{Colors.RESET} {demo.script}")
        print(f"{Colors.CYAN}Category:{Colors.RESET} {demo.category}")
        print(f"{Colors.CYAN}Difficulty:{Colors.RESET} {difficulty_color}{demo.difficulty}{Colors.RESET}")
        print(f"{Colors.CYAN}Estimated Time:{Colors.RESET} {demo.estimated_time}")
        print(f"\n{Colors.CYAN}Description:{Colors.RESET}")
        print(f"  {demo.description}")
        
        print(f"\n{Colors.CYAN}Features:{Colors.RESET}")
        for feature in demo.features:
            print(f"  • {feature}")
        
        if demo.requirements:
            print(f"\n{Colors.CYAN}Requirements:{Colors.RESET}")
            for req in demo.requirements:
                print(f"  • {req}")
        
        if prompt_yes_no("\nLaunch this demo?", default=False):
            self._launch_demo(demo)
    
    def view_launch_history(self):
        """View history of launched demos."""
        if not self.launch_history:
            print(f"{Colors.YELLOW}No demos launched yet{Colors.RESET}")
            return
        
        print(f"\n{Colors.BOLD}Launch History:{Colors.RESET}")
        
        for i, (timestamp, demo_name) in enumerate(self.launch_history, 1):
            print(f"{i}. {timestamp} - {demo_name}")
    
    def show_help(self):
        """Display help information."""
        help_text = f"""
{Colors.BOLD}Superego MCP Demo Dashboard Help{Colors.RESET}

This dashboard provides centralized access to all Superego MCP demos.

{Colors.BOLD}Demo Categories:{Colors.RESET}
• Basic - Simple demos for getting started
• Intermediate - More complex scenarios and patterns  
• Advanced - Full-featured demos with extensive options
• Utility - Development and testing tools

{Colors.BOLD}Difficulty Levels:{Colors.RESET}
• {Colors.GREEN}Beginner{Colors.RESET} - No prior knowledge required
• {Colors.YELLOW}Intermediate{Colors.RESET} - Some understanding of security concepts helpful
• {Colors.RED}Advanced{Colors.RESET} - Full understanding of Superego MCP concepts

{Colors.BOLD}Tips:{Colors.RESET}
• Start with Simple FastAgent Demo if you're new
• Use Interactive Hook Demo for exploring scenarios
• Run Security Scenarios Demo for comprehensive testing
• Use Scenario Runner for batch testing and metrics

{Colors.BOLD}Common Options:{Colors.RESET}
Most demos support these command-line options:
  --log-level    Set logging level (DEBUG, INFO, WARNING, ERROR)
  --rules        Path to custom security rules file
  --output       Output file for results
  --interactive  Run in interactive mode
"""
        print(help_text)
    
    def _launch_prompt(self, demos: Optional[List[DemoInfo]] = None):
        """Prompt to launch a demo from a list."""
        if demos is None:
            demos = self.demos
        
        launch = input("\nLaunch demo? Enter number (or 0 to cancel): ").strip()
        
        try:
            idx = int(launch) - 1
            if idx == -1:  # User entered 0
                return
            if 0 <= idx < len(demos):
                self._launch_demo(demos[idx])
        except ValueError:
            print(f"{Colors.YELLOW}Please enter a number{Colors.RESET}")
    
    def _launch_demo(self, demo: DemoInfo):
        """Launch a specific demo."""
        script_path = self.demo_dir / demo.script
        
        if not script_path.exists():
            print(f"{Colors.RED}Demo script not found: {script_path}{Colors.RESET}")
            return
        
        print(f"\n{Colors.GREEN}Launching {demo.name}...{Colors.RESET}")
        print(f"Script: {demo.script}")
        print(f"Estimated time: {demo.estimated_time}\n")
        
        # Record launch
        self.launch_history.append((format_timestamp(), demo.name))
        
        # Launch the demo
        try:
            # Use sys.executable to ensure we use the same Python interpreter
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(self.demo_dir)
            )
            
            if result.returncode == 0:
                print(f"\n{Colors.GREEN}Demo completed successfully{Colors.RESET}")
            else:
                print(f"\n{Colors.YELLOW}Demo exited with code: {result.returncode}{Colors.RESET}")
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Demo interrupted by user{Colors.RESET}")
        except Exception as e:
            print(f"\n{Colors.RED}Error launching demo: {e}{Colors.RESET}")
    
    def run(self):
        """Main entry point for the dashboard."""
        self.show_welcome()
        
        while True:
            self.show_main_menu()
            choice = input("\nChoice: ").strip()
            
            if choice == "1":
                self.browse_all_demos()
            elif choice == "2":
                self.browse_by_category()
            elif choice == "3":
                self.browse_by_difficulty()
            elif choice == "4":
                self.quick_launch()
            elif choice == "5":
                self.search_demos()
            elif choice == "6":
                self.view_demo_details()
            elif choice == "7":
                self.view_launch_history()
            elif choice == "8":
                self.show_help()
            elif choice == "9":
                if prompt_yes_no("\nExit dashboard?", default=False):
                    break
            else:
                print(f"{Colors.YELLOW}Invalid choice{Colors.RESET}")
        
        print(f"\n{Colors.CYAN}Thank you for using Superego MCP Demo Dashboard!{Colors.RESET}")


def main():
    """Main entry point."""
    try:
        dashboard = DemoDashboard()
        dashboard.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Dashboard interrupted{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()