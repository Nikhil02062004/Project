import click
import json
import sys
from typing import Optional

from .core.queue import JobQueue
from .core.worker import WorkerManager
from .core.job import Job, JobState
from .persistence.sqlite_store import SQLiteJobStore

@click.group()
@click.pass_context
def cli(ctx):
    """QueueCTL - Background Job Queue System"""
    ctx.ensure_object(dict)
    
    storage = SQLiteJobStore()
    queue = JobQueue(storage)
    worker_manager = WorkerManager(queue)
    
    ctx.obj['storage'] = storage
    ctx.obj['queue'] = queue
    ctx.obj['worker_manager'] = worker_manager

@cli.command()
@click.argument('job_spec')
@click.pass_context
def enqueue(ctx, job_spec):
    """Enqueue a new job"""
    try:
       
        try:
            job_data = json.loads(job_spec)
            command = job_data.get('command')
            job_id = job_data.get('id')
            max_retries = job_data.get('max_retries')
        except json.JSONDecodeError:
            
            command = job_spec
            job_id = None
            max_retries = None
        
        if not command:
            raise click.ClickException("Job must have a command")
        
        queue = ctx.obj['queue']
        job = queue.enqueue(command, job_id, max_retries)
        
        click.echo(f"Enqueued job {job.id}: {job.command}")
        
    except Exception as e:
        raise click.ClickException(f"Failed to enqueue job: {str(e)}")


@cli.group()
def worker():
    """Manage worker processes"""
    pass

@worker.command()
@click.option('--count', default=1, help='Number of workers to start')
@click.pass_context
def start(ctx, count):
    """Start worker processes"""
    worker_manager = ctx.obj['worker_manager']
    worker_manager.start_workers(count)
    
   
    try:
        while worker_manager.get_active_workers():
            click.echo(f"Workers running... (Active: {len(worker_manager.get_active_workers())})")
            import time
            time.sleep(5)
    except KeyboardInterrupt:
        click.echo("\nShutting down workers...")
        worker_manager.stop_workers()

@worker.command()
@click.pass_context
def stop(ctx):
    """Stop all worker processes"""
    worker_manager = ctx.obj['worker_manager']
    worker_manager.stop_workers()

@cli.command()
@click.pass_context
def status(ctx):
    """Show system status"""
    queue = ctx.obj['queue']
    worker_manager = ctx.obj['worker_manager']
    
    # Job statistics
    stats = queue.get_stats()
    worker_stats = worker_manager.get_worker_stats()
    
    click.echo("=== Queue Status ===")
    for state in JobState:
        count = stats.get(state.value, 0)
        click.echo(f"{state.value.capitalize()}: {count}")
    
    click.echo("\n=== Worker Status ===")
    click.echo(f"Total Workers: {worker_stats['total']}")
    click.echo(f"Working: {worker_stats['working']}")
    click.echo(f"Idle: {worker_stats['idle']}")

@cli.command()
@click.option('--state', type=click.Choice([s.value for s in JobState]), 
              help='Filter jobs by state')
@click.pass_context
def list(ctx, state):
    """List jobs"""
    queue = ctx.obj['queue']
    
    if state:
        jobs = queue.list_jobs(JobState(state))
    else:
        jobs = queue.list_jobs()
    
    for job in jobs:
        click.echo(f"{job.id}: {job.command} [{job.state.value}] (attempts: {job.attempts}/{job.max_retries})")

# FIXED: DLQ as a command group
@cli.group()
def dlq():
    """Dead Letter Queue operations"""
    pass

@dlq.command()
@click.pass_context
def list(ctx):
    """List DLQ jobs"""
    queue = ctx.obj['queue']
    dlq_jobs = queue.get_dlq_jobs()
    
    if not dlq_jobs:
        click.echo("No jobs in DLQ")
        return
    
    for job in dlq_jobs:
        click.echo(f"{job.id}: {job.command} (failed after {job.attempts} attempts)")
        if job.last_error:
            click.echo(f"  Error: {job.last_error}")

@dlq.command()
@click.argument('job_id')
@click.pass_context
def retry(ctx, job_id):
    """Retry a job from DLQ"""
    queue = ctx.obj['queue']
    
    if queue.retry_dlq_job(job_id):
        click.echo(f"Job {job_id} moved back to pending state")
    else:
        click.echo(f"Job {job_id} not found in DLQ or cannot be retried")

# FIXED: Config as a command group
@cli.group()
def config():
    """Configuration management"""
    pass

@config.command('set')
@click.argument('key')
@click.argument('value')
@click.pass_context
def config_set(ctx, key, value):
    """Set configuration value"""
    storage = ctx.obj['storage']
    
    # Try to parse value as JSON, fallback to string
    try:
        value_parsed = json.loads(value)
    except json.JSONDecodeError:
        value_parsed = value
    
    storage.set_config(key, value_parsed)
    click.echo(f"Set {key} = {value_parsed}")

@config.command('get')
@click.argument('key')
@click.pass_context
def config_get(ctx, key):
    """Get configuration value"""
    storage = ctx.obj['storage']
    value = storage.get_config(key)
    
    if value is not None:
        click.echo(f"{key} = {value}")
    else:
        click.echo(f"Configuration key '{key}' not found")

def main():
    cli(obj={})

if __name__ == '__main__':
    main()