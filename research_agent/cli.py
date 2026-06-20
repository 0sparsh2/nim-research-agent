import argparse
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from research_agent.agent import ResearchAgent

load_dotenv()
console = Console()

def main():
    parser = argparse.ArgumentParser(
        description="NIM Research Agent: Autonomous internet researcher using NVIDIA NIM APIs."
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        required=True,
        help="The core topic or query to research."
    )
    parser.add_argument(
        "--instructions", "-i",
        type=str,
        default="",
        help="Specific guidelines or formatting preferences."
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="research_report.md",
        help="Output filename for the research report (Markdown)."
    )
    parser.add_argument(
        "--max-steps", "-s",
        type=int,
        default=12,
        help="Maximum loop steps for the agent."
    )
    
    args = parser.parse_args()
    
    console.print(Panel.fit(
        f"[bold green]Starting Autonomous Research Agent[/bold green]\n"
        f"[bold blue]Query:[/bold blue] {args.query}\n"
        f"[bold yellow]Output File:[/bold yellow] {args.output}\n"
        f"[bold white]Max Steps:[/bold white] {args.max_steps}",
        title="NIM DeepResearch"
    ))
    
    agent = ResearchAgent(max_steps=args.max_steps)
    
    try:
        with console.status("[bold cyan]Agent is performing research on the internet (searching & crawling)...[/bold cyan]", spinner="dots"):
            report = agent.run(args.query, args.instructions)
            
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
            
        console.print(f"\n[bold green]✓ Research completed successfully![/bold green]")
        console.print(f"Report written to: [bold white]{args.output}[/bold white]")
    except Exception as e:
        Console(stderr=True).print(f"\n[bold red]✗ Research failed:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
