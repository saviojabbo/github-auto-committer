import os
import random
from datetime import datetime, timedelta
import pytz
from git import Repo
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pathlib import Path
import yaml
from dotenv import load_dotenv

class GitAutoCommitter:
    def __init__(self, config_path='config.yaml'):
        self.load_config(config_path)
        self.setup_logging()
        self.setup_repository()
        self.scheduler = BackgroundScheduler(timezone=self.config['schedule']['timezone'])

    def load_config(self, config_path):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        load_dotenv()

    def setup_logging(self):
        logger.add(
            self.config['logging']['log_file'],
            level=self.config['logging']['level'],
            rotation="1 day"
        )

    def setup_repository(self):
        repo_path = Path('./repo')
        if not repo_path.exists():
            self.repo = Repo.clone_from(
                self.config['github']['repository'],
                repo_path,
                branch=self.config['github']['branch']
            )
        else:
            self.repo = Repo(repo_path)
        
        # Configure Git credentials
        self.repo.git.config('user.email', os.getenv('GIT_EMAIL'))
        self.repo.git.config('user.name', os.getenv('GIT_USERNAME'))

    def generate_commit_times(self):
        num_commits = random.randint(1, 10)
        start_time = datetime.strptime(self.config['schedule']['start_time'], '%H:%M')
        end_time = datetime.strptime(self.config['schedule']['end_time'], '%H:%M')

        time_range = (end_time - start_time).seconds
        commit_times = []

        for _ in range(num_commits):
            random_seconds = random.randint(0, time_range)
            commit_time = start_time + timedelta(seconds=random_seconds)
            commit_times.append(commit_time.time())

        return sorted(commit_times)

    def make_commit(self):
        try:
            commit_file = Path(self.repo.working_dir) / self.config['github']['commit_file']
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(commit_file, 'a') as f:
                f.write(f'Commit made at: {timestamp}\n')

            self.repo.index.add([str(commit_file)])
            commit_message = f'Auto commit at {timestamp}'
            self.repo.index.commit(commit_message)
            
            # Push changes
            origin = self.repo.remote()
            origin.push()

            logger.info(f'Successfully made commit at {timestamp}')

        except Exception as e:
            logger.error(f'Error making commit: {str(e)}')

    def schedule_daily_commits(self):
        # Clear existing jobs
        self.scheduler.remove_all_jobs()

        # Schedule job to create new commit schedule each day at midnight
        self.scheduler.add_job(
            self.create_daily_schedule,
            CronTrigger(hour=0, minute=0),
            name='create_schedule'
        )

        # Create first schedule immediately
        self.create_daily_schedule()

    def create_daily_schedule(self):
        commit_times = self.generate_commit_times()
        
        for commit_time in commit_times:
            self.scheduler.add_job(
                self.make_commit,
                CronTrigger(
                    hour=commit_time.hour,
                    minute=commit_time.minute
                ),
                name=f'commit_{commit_time}'
            )
            
        logger.info(f'Scheduled {len(commit_times)} commits for today')

    def start(self):
        self.schedule_daily_commits()
        self.scheduler.start()
        logger.info('Auto committer started successfully')

    def stop(self):
        self.scheduler.shutdown()
        logger.info('Auto committer stopped')