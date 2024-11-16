#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2024-      Sebastian Helms           Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.10
#  and up.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import os
from shutil import rmtree
from pathlib import Path

from lib.model.smartplugin import SmartPlugin
from .webif import WebInterface
from .gperror import GPError

from github import Auth
from github import Github
from git import Repo


class GitHubHelper(object):
    """ Helper class for handling the GitHub API """

    def loggerr(self, msg):
        """ log error message and raise GPError to signal WebIf """

        # TODO: this need to be reworked if WebIf errors should be displayed in German or translated
        self.logger.error(msg)
        raise GPError(msg)

    def __init__(self, dt, logger, repo='plugins', apikey='', auth=None, **kwargs):
        self.dt = dt
        self.logger = logger
        self.apikey = apikey
        # allow auth only, if apikey is set
        if auth is None:
            self.auth = bool(self.apikey)
        else:
            self.auth = auth and bool(self.apikey)

        # name of the repo, at present always 'plugins'
        self.repo = repo

        # github class instance
        self._github = None

        # contains a list of all smarthomeNG/plugins forks after fetching from GitHub:
        #
        # self.forks = {
        #   'owner': {
        #     'repo': git.Repo(path),
        #     'branches': {  # (optional!)
        #       '<branch1>': {'branch': git.Branch(name="<branch1>"), 'repo': git.Repo(path)', 'owner': '<owner>'}, 
        #       '<branch2>': {...}
        #     }
        #   }
        # }
        #
        # the 'branches' key and data is only inserted after branches have been fetched from github
        # repo and owner info are identical to the forks' data and present for branches return data
        # outside the self.forks dict
        self.forks = {}

        # contains a list of all PRs of smarthomeNG/plugins after fetching from GitHub:
        #
        # self.pulls = {
        #     <PR1 number>: {'title': '<title of the PR>', 'pull': github.PullRequest(title, number), 'git_repo': git.Repo(path), 'owner': '<fork owner>', 'repo': 'plugins', 'branch': '<branch>'},
        #     <PR2 number>: {...}
        # }
        #
        # as this is the GitHub PR data, no information is present which plugin "really" is
        # changed in the PR, need to identify this later
        self.pulls = {}

        # keeps the git.Repo() for smarthomeNG/plugins
        self.git_repo = None

    def login(self):
        try:
            if self.auth:
                auth = Auth.Token(self.apikey)
            else:
                auth = None

            self._github = Github(auth=auth, retry=None)

            if auth:
                self._github.get_user().login

            if not self._github:
                raise GPError('setup/login failed')
        except Exception as e:
            self._github = None
            self.loggerr(f'could not initialize Github object: {e}')

    def get_rate_limit(self):
        """ return list of allowed and remaining requests and backoff seconds """
        try:
            rl = self._github.get_rate_limit()
            allow = rl.core.limit
            remain = rl.core.remaining
            backoff = (rl.core.reset - self.dt.now()).total_seconds()
            if backoff < 0:
                backoff = 0
        except Exception as e:
            self.logger.warning(f'error while getting rate limits: {e}')
            return [0, 0, 0]

        return [allow, remain, backoff]

    def get_repo(self, user, repo):
        if not self._github:
            self.login()

        try:
            return self._github.get_repo(f'{user}/{repo}')
        except Exception:
            pass

    def set_repo(self) -> bool:
        if not self._github:
            self.login()

        self.git_repo = self.get_repo('smarthomeNG', self.repo)
        return True

    def get_pulls(self, fetch=False) -> bool:
        if not self._github:
            self.login()

        if not self.git_repo:
            self.set_repo()

        # succeed if cached pulls present and fetch not requested
        if not fetch:
            if self.pulls != {}:
                self.logger.debug(f'using cached pulls: {self.pulls.keys()}')
                return True

        self.logger.debug('fetching pulls from github')
        self.pulls = {}
        try:
            for pull in self.git_repo.get_pulls():
                self.pulls[pull.number] = {
                    'title': pull.title,
                    'pull': pull,
                    'git_repo': pull.head.repo,
                    'owner': pull.head.repo.owner.login,
                    'repo': pull.head.repo.name,
                    'branch': pull.head.ref
                }
        except AttributeError:
            self.logger.warning('github object not created. Check rate limit.')
            return False

        return True

    def get_forks(self, fetch=False) -> bool:
        if not self._github:
            self.login()

        if not self.git_repo:
            self.set_repo()

        # succeed if cached forks present and fetch not requested
        if not fetch:
            if self.forks != {}:
                return True

        self.forks = {}
        try:
            for fork in self.git_repo.get_forks():
                self.forks[fork.full_name.split('/')[0]] = {'repo': fork}
        except AttributeError:
            self.logger.warning('github object not created. Check rate limit.')
            return False

        return True

    def get_branches_from(self, fork=None, owner='', fetch=False) -> dict:

        if fork is None and owner:
            try:
                fork = self.forks[owner]['repo']
            except Exception:
                pass
        if not fork:
            return {}

        # if not specifically told to fetch from github -
        if not fetch:
            # try to get cached branches
            try:
                b_list = self.forks[fork.owner.login]['branches']
            except KeyError:
                pass
            else:
                self.logger.debug(f'returning cached {b_list}')
                return b_list

        # fetch from github
        self.logger.debug('refreshing branches from github')
        branches = fork.get_branches()
        b_list = {}
        for branch in branches:
            b_list[branch.name] = {'branch': branch, 'repo': fork, 'owner': fork.owner.login}

        self.forks[fork.owner.login]['branches'] = b_list
        return b_list

    def get_plugins_from(self, fork=None, owner='', branch='', fetch=False) -> list:

        if not branch:
            return []

        if fork is None and owner:
            try:
                fork = self.forks[owner]['repo']
            except Exception:
                pass

        if not fork:
            return []

        # if not specifically told to fetch from github, -
        if not fetch:
            # try to get cached plugin list
            try:
                plugins = self.forks[fork.owner.login]['branches'][branch]['plugins']
            except KeyError:
                pass
            else:
                self.logger.debug(f'returning cached plugins {plugins}')
                return plugins

        # plugins not yet cached, fetch from github
        self.logger.debug('fetching plugins from github')
        contents = fork.get_contents("", ref=branch)
        plugins = [item.path for item in contents if item.type == 'dir' and not item.path.startswith('.')]

        try:
            # add plugins to branch entry, if present
            b = self.forks[fork.owner.login]['branches'][branch]
            b['plugins'] = plugins
        except KeyError:
            pass
        return sorted(plugins)


class GithubPlugin(SmartPlugin):
    """
    This class supports testing foreign plugins by letting the user select a
    shng plugins fork and branch, and then setting up a local repo containing
    that fork. Additionally, the specified plugin will be soft-linked into the
    "live" plugins repo worktree as a private plugin.
    """
    PLUGIN_VERSION = '1.0.0'
    REPO_DIR = 'priv_repos'

    def loggerr(self, msg):
        """ log error message and raise GPError to signal WebIf """
        self.logger.error(msg)
        raise GPError(msg)

    def __init__(self, sh):
        super().__init__()

        # self.repos enthält die Liste der lokal eingebundenen Fremd-Repositories
        # mit den jeweils zugehörigen Daten über das installierte Plugin, den
        # jeweiligen Worktree/Branch und Pfadangaben.
        #
        # self.repos = {
        #   '<id1>': {
        #     'plugin': '<plugin>',                                 # Name des installierten Plugins
        #     'owner': '<owner>',                                    # Owner des GitHub-Forks
        #     'branch': '<branch>'',                                # Branch im GitHub-Fork
        #     'gh_repo': 'plugins',                                 # fix, Repo smarthomeNG/plugins
        #     'url': f'https://github.com/{owner}/plugins.git',     # URL des Forks
        #     'repo_path': repo_path,                               # absoluter Pfad zum Repo
        #     'wt_path': wt_path,                                   # absoluter Pfad zum Worktree
        #     'disp_wt_path': 'plugins/priv_repos/...'              # relativer Pfad zum Worktree vom shng-Basisverzeichnis aus
        #     'rel_wt_path': os.path.join('..', '..', wt_path),     # relativer Pfad zum Worktree vom Repo aus
        #     'link': os.path.join('plugins', f'priv_{plugin}'),    # absoluter Pfad-/Dateiname des Plugin-Symlinks
        #     'rel_link_path': os.path.join(wt_path, plugin),       # Ziel der Plugin-Symlinks: relativer Pfad des Ziel-Pluginordners "unterhalb" von plugins/
        #     'repo': repo,                                         # git.Repo(path)
        #     'clean': bool                                         # repo is clean and synced?
        #   },
        #   '<id2>': {...}
        # }
        self.repos = {}

        # to make sure we really hit the right path, don't use relative paths
        # but use shngs BASE path attribute
        self.plg_path = os.path.join(self._sh.BASE, 'plugins')
        self.repo_path = os.path.join(self.plg_path, self.REPO_DIR)

        # make plugins/priv_repos if not present
        if not os.path.exists(self.repo_path):
            self.logger.debug(f'creating repo dir {self.repo_path}')
            os.mkdir(self.repo_path)

        self.gh_apikey = self.get_parameter_value('app_token')
        self.gh = GitHubHelper(self._sh.shtime, apikey=self.gh_apikey, logger=self.logger)

        self.init_webinterface(WebInterface)

    #
    # methods for handling local repos
    #

    def read_repos_from_dir(self, exc=False):
        # clear stored repos
        self.repos = {}

        # plugins/priv_repos not present -> no previous plugin action
        if not os.path.exists(self.repo_path):
            return

        self.logger.debug('checking plugin links')
        pathlist = Path(self.plg_path).glob('priv_*')
        for item in pathlist:
            if not item.is_symlink():
                self.logger.debug(f'ignoring {item}, is not symlink')
                continue
            target = os.path.join(self.plg_path, os.readlink(str(item)))
            if not os.path.isdir(target):
                self.logger.debug(f'ignoring link {item}, target {target} is not directory')
                continue
            try:
                # plugins/priv_repos/foo_wt_bar/baz/ ->
                # pr = 'priv_repos'
                # wt = 'foo_wt_bar'
                # plugin = 'baz'
                pr, wt, plugin = self._get_last_3_path_parts(target)
                if pr != 'priv_repos' or '_wt_' not in wt:
                    self.logger.debug(f'ignoring {target}, not in priv_repos/*_wt_*/plugin form ')
                    continue
            except Exception:
                continue

            try:
                # owner_wt_branch
                owner, branch = wt.split('_wt_')
            except Exception:
                self.logger.debug(f'ignoring {target}, not in priv_repos/*_wt_*/plugin form ')
                continue

            # surely it is possible to deduce the different path names from previously uses paths
            # but this seems more consistent...
            wtpath, _ = os.path.split(target)
            repo = Repo(wtpath)
            repo_path = os.path.join(self.repo_path, owner)
            wt_path = os.path.join(self.repo_path, f'{owner}_wt_{branch}')

            # use part of link name after ".../plugins/priv_"
            name = str(item)[len(self.plg_path) + 6:]

            self.repos[name] = {
                'plugin': plugin,
                'owner': owner,
                'branch': branch,
                'gh_repo': 'plugins',
                'url': f'https://github.com/{owner}/plugins.git',
                'repo_path': repo_path,
                'wt_path': wt_path,
                'disp_wt_path': wt_path[len(self._sh.BASE) + 1:],
                'rel_wt_path': os.path.join('..', f'{owner}_wt_{branch}'),
                'link': str(item),
                'rel_link_path': str(target),
                'repo': repo,
            }
            self.repos[name]['clean'] = self.is_repo_clean(name, exc)

    def check_for_repo_name(self, name) -> bool:
        """ check if name exists in repos or link exists """
        if name in self.repos or os.path.exists(os.path.join(self.plg_path, 'priv_' + name)):
            self.loggerr(f'name {name} already taken, delete old plugin first or choose a different name.')
            return False

        return True

    def create_repo(self, name, owner, plugin, branch=None) -> bool:
        """ create repo from given parameters """

        try:
            self.check_for_repo_name(name)
        except Exception as e:
            self.loggerr(e)
            return False

        if not owner or not plugin:
            self.loggerr(f'Insufficient parameters, github user {owner} or plugin {plugin} empty, unable to fetch repo, aborting.')
            return False

        # if branch is not given, assume that the branch is named like the plugin
        if not branch:
            branch = plugin

        repo = {
            'plugin': plugin,
            'owner': owner,
            'branch': branch,
            'plugin': plugin,
            # default to plugins repo. No further repos are managed right now
            'gh_repo': 'plugins'
        }

        # build GitHub url from parameters. Hope they don't change the syntax...
        repo['url'] = f'https://github.com/{owner}/{repo["gh_repo"]}.git'

        # path to git repo dir, default to "plugins/priv_repos/{owner}"
        repo['repo_path'] = os.path.join(self.repo_path, owner)

        # üath to git worktree dir, default to "plugins/priv_repos/{owner}_wt_{branch}"
        repo['wt_path'] = os.path.join(self.repo_path, f'{owner}_wt_{branch}')
        repo['disp_wt_path'] = repo['wt_path'][len(self._sh.BASE) + 1:]
        repo['rel_wt_path'] = os.path.join('..', f'{owner}_wt_{branch}')

        # set link location from plugin name
        repo['link'] = os.path.join(self.plg_path, f'priv_{name}')
        repo['rel_link_path'] = os.path.join(self.REPO_DIR, f'{owner}_wt_{branch}', plugin)

        # make plugins/priv_repos if not present
        if not os.path.exists(self.repo_path):
            self.logger.debug(f'creating dir {self.repo_path}')
            os.mkdir(self.repo_path)

        self.logger.debug(f'check for repo at {repo["repo_path"]}...')

        if os.path.exists(repo['repo_path']) and os.path.isdir(repo['repo_path']):
            # path exists, try to load existing repo
            repo['repo'] = Repo(repo['repo_path'])

            self.logger.debug(f'found repo {repo["repo"]} at {repo["repo_path"]}')

            if "origin" not in repo['repo'].remotes:
                self.loggerr(f'repo at {repo["repo_path"]} has no "origin" remote set')
                return False

            origin = repo['repo'].remotes.origin
            if origin.url != repo['url']:
                self.loggerr(f'origin of existing repo is {origin.url}, expecting {repo["url"]}')
                return False

        else:
            self.logger.debug(f'cloning repo at {repo["repo_path"]} from {repo["url"]}...')

            # clone repo from url
            repo['repo'] = Repo.clone_from(repo['url'], repo['repo_path'])

        # fetch repo data
        self.logger.debug('fetching from origin...')
        repo['repo'].remotes.origin.fetch()

        wtr = ''

        # cleanup worktrees (just in case...)
        try:
            self.logger.debug('pruning worktree')
            repo['repo'].git.worktree('prune')
        except Exception:
            pass

        # setup worktree
        if not os.path.exists(repo['wt_path']):
            self.logger.debug(f'creating worktree at {repo["wt_path"]}...')
            wtr = repo['repo'].git.worktree('add', repo['rel_wt_path'], repo['branch'])

        # path exists, try to load existing worktree
        repo['wt'] = Repo(repo['wt_path'])
        self.logger.debug(f'found worktree {repo["wt"]} at {repo["wt_path"]}')

        # worktree not created from branch, checkout branch of existing worktree manually
        if not wtr:
            # get remote branch ref
            rbranch = getattr(repo['repo'].remotes.origin.refs, repo['branch'])
            if not rbranch:
                self.loggerr(f'Ref {repo["branch"]} not found at origin {repo["url"]}')
                return False

            # create local branch
            self.logger.debug(f'creating local branch {repo["branch"]}')
            try:
                branchref = repo['wt'].create_head(repo['branch'], rbranch)
                branchref.set_tracking_branch(rbranch)
                branchref.checkout()
            except Exception as e:
                self.loggerr(f'setting up local branch {repo["branch"]} failed: {e}')
                return False

        repo['clean'] = True

        self.logger.debug(f'creating link {repo["link"]} to {repo["rel_link_path"]}...')
        try:
            os.symlink(repo['rel_link_path'], repo['link'])
        except FileExistsError:
            self.loggerr(f'plugin link {repo["link"]} was created by someone else while we were setting up repo. Not overwriting, check link file manually')

        self.repos[name] = repo

        return True

    def remove_plugin(self, name) -> bool:
        """ remove plugin link, worktree and if not longer needed, local repo """
        if name not in self.repos:
            self.loggerr(f'plugin entry {name} not found.')
            return False

        if not self.is_repo_clean(name):
            self.loggerr(f'repo {name} is not synced or dirty, not removing.')
            return False

        # get all data to remove
        repo = self.repos[name]
        link_path = repo['link']
        wt_path = repo['wt_path']
        repo_path = repo['repo_path']
        owner = repo['owner']
        # check if repo is used by other plugins
        last = True
        for r in self.repos:
            if r == name:
                continue
            if self.repos[r]["owner"] == owner:
                last = False
                break

        err = []
        try:
            self.logger.debug(f'removing link {link_path}')
            os.remove(link_path)
        except Exception as e:
            err.append(e)
        try:
            self.logger.debug(f'removing worktree {wt_path}')
            rmtree(wt_path)
        except Exception as e:
            err.append(e)
        try:
            self.logger.debug('pruning worktree')
            repo['repo'].git.worktree('prune')
        except Exception as e:
            err.append(e)
        if last:
            try:
                self.logger.debug(f'repo {repo_path} is no longer used, removing')
                rmtree(repo_path)
            except Exception as e:
                err.append(e)

        # remove repo entry from plugin dict
        del self.repos[name]
        del repo

        if err:
            msg = ", ".join([str(x) for x in err])
            self.loggerr(f'error(s) occurred while removing plugin: {msg}')
            return False

        return True

    #
    # github API methods
    #

    def is_repo_clean(self, name: str, exc=False) -> bool:
        """ checks if worktree is clean and local and remote branches are in sync """
        if name not in self.repos:
            self.loggerr(f'repo {name} not found')
            return False

        entry = self.repos[name]
        local = entry['repo']

        # abort if worktree isn't clean
        if local.is_dirty() or local.untracked_files != []:
            self.repos[name]['clean'] = False
            return False

        # get remote and local branch heads
        try:
            remote = self.gh.get_repo(entry['owner'], entry['gh_repo'])
            r_branch = remote.get_branch(branch=entry['branch'])
            l_head = local.heads[entry['branch']].commit.hexsha
            r_head = r_branch.commit.sha
        except AttributeError:
            if exc:
                f = self.loggerr
            else:
                f = self.logger.warning
            f(f'error while checking sync status for {name}. Rate limit active?')
            return False
        except Exception as e:
            self.loggerr(f'error while checking sync status for {name}: {e}')
            return False

        clean = l_head == r_head
        self.repos[name]['clean'] = clean
        return clean

    def pull_repo(self, name: str) -> bool:
        """ pull repo if clean """
        if not name or name not in self.repos:
            self.loggerr(f'repo {name} invalid or not found')
            return False

        try:
            res = self.is_repo_clean(name)
            if not res:
                raise GPError('worktree not clean')
        except Exception as e:
            self.loggerr(f'error checking repo {name}: {e}')
            return False

        repo = self.repos[name]['repo']
        org = None
        try:
            org = repo.remotes.origin
        except Exception:
            if len(repo.remotes) > 0:
                org = repo.remotes.get('origin')

        if org is None:
            self.loggerr(f'remote "origin" not found in remotes {repo.remotes}')
            return False

        try:
            org.pull()
            return True
        except Exception as e:
            self.loggerr(f'error while pulling: {e}')

    def setup_github(self) -> bool:
        """ login to github and set repo """
        try:
            self.gh.login()
        except Exception as e:
            self.loggerr(f'error while logging in to GitHub: {e}')
            return False

        return self.gh.set_repo()

    def fetch_github_forks(self, fetch=False) -> bool:
        """ fetch forks from github API """
        if self.gh:
            return self.gh.get_forks(fetch=fetch)
        else:
            return False

    def fetch_github_pulls(self, fetch=False) -> bool:
        """ fetch PRs from github API """
        if self.gh:
            return self.gh.get_pulls(fetch=fetch)
        else:
            return False

    def fetch_github_branches_from(self, fork=None, owner='', fetch=False) -> dict:
        """
        fetch branches for given fork from github API

        if fork is given as fork object, use this
        if owner is given and present in self.forks, use their fork object
        """
        return self.gh.get_branches_from(fork=fork, owner=owner, fetch=fetch)

    def fetch_github_plugins_from(self, fork=None, owner='', branch='', fetch=False) -> list:
        """ fetch plugin names for selected fork/branch """
        return self.gh.get_plugins_from(fork=fork, owner=owner, branch=branch, fetch=fetch)

    def get_github_forks(self, owner=None) -> dict:
        """ return forks or single fork for given owner """
        if owner:
            return self.gh.forks.get(owner, {})
        else:
            return self.gh.forks

    def get_github_forklist_sorted(self) -> list:
        """ return list of forks, sorted alphabetically, used forks up front """

        # case insensitive sorted forks
        forks = sorted(self.get_github_forks().keys(), key=lambda x: x.casefold())
        sforkstop = []
        sforks = []

        # existing owners in self.repos
        owners = [v['owner'] for k, v in self.repos.items()]

        for f in forks:
            if f in owners:
                # put at top of list
                sforkstop.append(f)
            else:
                # put in nowmal list below
                sforks.append(f)

        return sforkstop + sforks

    def get_github_pulls(self, number=None) -> dict:
        """ return pulls or single pull for given number """
        if number:
            return self.gh.pulls.get(number, {})
        else:
            return self.gh.pulls

    #
    # methods to run git actions based on github data
    #

    # unused right now, possibly remove?
    def create_repo_from_gh(self, number=0, owner='', branch=None, plugin='') -> bool:
        """
        call init/create methods to download new repo and create worktree

        if number is given, the corresponding PR is used for identifying the branch
        if branch is given, it is used

        if plugin is given, it is used as plugin name. otherwise, we will try to
        deduce it from the PR title or use the branch name
        """
        r_owner = ''
        r_branch = ''
        r_plugin = plugin

        if number:
            # get data from given PR
            pr = self.get_github_pulls(number=number)
            if pr:
                r_owner = pr['owner']
                r_branch = pr['branch']
                # try to be smart about the plugin name
                if not r_plugin:
                    if ':' in pr['title']:
                        r_plugin, _ = pr['title'].split(':', maxsplit=1)
                    elif ' ' in pr['name']:
                        r_plugin, _ = pr['title'].split(' ', maxsplit=1)
                    else:
                        r_plugin = pr['title']
                    if r_plugin.lower().endswith(' plugin'):
                        r_plugin = r_plugin[:-7].strip()

        elif branch is not None and type(branch) is str and owner is not None:
            # just take given data
            r_owner = owner
            r_branch = branch
            if not r_plugin:
                r_plugin = branch

        elif branch is not None:
            # search for branch object in forks.
            # Will not succeed if branches were not fetched for this fork earlier...
            for user in self.gh.forks:
                if 'branches' in self.gh.forks[user]:
                    for b in self.gh.forks[user]['branches']:
                        if self.gh.forks[user]['branches'][b]['branch'] is branch:
                            r_owner = user
                            r_branch = b
                            if not r_plugin:
                                r_plugin = b

        # do some sanity checks on given data
        if not r_owner or not r_branch or not r_plugin:
            self.loggerr(f'unable to identify repo from owner "{r_owner}", branch "{r_branch}" and plugin "{r_plugin}"')
            return False

        if r_owner not in self.gh.forks:
            self.loggerr(f'smarthomeNG/plugins fork by owner {r_owner} not found')
            return False

        if 'branches' in self.gh.forks[r_owner] and r_branch not in self.gh.forks[r_owner]['branches']:
            self.loggerr(f'branch {r_branch} not found in cached branches for owner {r_owner}. Maybe re-fetch branches?')

        # default id for plugin (actually not identifying the plugin but the branch...)
        name = f'{r_owner}/{r_branch}'

        return self.create_repo(name, r_owner, r_plugin.lower(), r_branch)

    #
    # general plugin methods
    #

    def run(self):
        self.logger.dbghigh(self.translate("Methode '{method}' aufgerufen", {'method': 'run()'}))
        self.alive = True     # if using asyncio, do not set self.alive here. Set it in the session coroutine

        try:
            self.setup_github()
            self.fetch_github_pulls()
            self.fetch_github_forks()
            self.read_repos_from_dir()
        except GPError:
            pass

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.dbghigh(self.translate("Methode '{method}' aufgerufen", {'method': 'stop()'}))
        self.alive = False     # if using asyncio, do not set self.alive here. Set it in the session coroutine

    #
    # helper methods
    #

    def _get_last_3_path_parts(self, path):
        """ return last 3 parts of a path """
        try:
            head, l3 = os.path.split(path)
            head, l2 = os.path.split(head)
            _, l1 = os.path.split(head)
            return (l1, l2, l3)
        except Exception:
            return ('', '', '')
