"""
This module is responsible for setup of executors defined in buildtest
configuration. The BuildExecutor class initializes the executors and chooses the
executor class (LocalExecutor, LSFExecutor, SlurmExecutor, CobaltExecutor) to call depending
on executor name.
"""

import logging
import multiprocessing as mp
import os

from buildtest.buildsystem.base import BuilderBase
from buildtest.defaults import BUILDTEST_EXECUTOR_DIR
from buildtest.exceptions import ExecutorError
from buildtest.executors.base import BaseExecutor
from buildtest.executors.cobalt import CobaltExecutor
from buildtest.executors.local import LocalExecutor
from buildtest.executors.lsf import LSFExecutor
from buildtest.executors.pbs import PBSExecutor
from buildtest.executors.slurm import SlurmExecutor
from buildtest.utils.file import create_dir, write_file

logger = logging.getLogger(__name__)


class BuildExecutor:
    """A BuildExecutor is responsible for initialing executors from buildtest configuration
    file which provides a list of executors. This class keeps track of all executors and provides
    the following methods:

    **setup**: This method will  write executor's ``before_script.sh``  that is sourced in each test upon calling executor.
    **run**: Responsible for invoking executor's **run** method based on builder object which is of type BuilderBase.
    **poll**: This is responsible for invoking ``poll`` method for corresponding executor from the builder object by checking job state
    """

    def __init__(self, site_config, max_pend_time=None):
        """Initialize executors, meaning that we provide the buildtest
        configuration that are validated, and can instantiate
        each executor to be available.

        :param site_config: the site configuration for buildtest.
        :type site_config: SiteConfiguration class, required
        """

        # stores a list of builders objects
        self.builders = []

        # store a list of valid builders
        self.valid_builders = []

        self.executors = {}
        logger.debug("Getting Executors from buildtest settings")
        active_system = site_config.name()
        if site_config.localexecutors:
            for name in site_config.localexecutors:
                self.executors[f"{active_system}.local.{name}"] = LocalExecutor(
                    f"{active_system}.local.{name}",
                    site_config.target_config["executors"]["local"][name],
                    site_config,
                )

        if site_config.slurmexecutors:
            for name in site_config.slurmexecutors:
                self.executors[f"{active_system}.slurm.{name}"] = SlurmExecutor(
                    f"{active_system}.slurm.{name}",
                    site_config.target_config["executors"]["slurm"][name],
                    site_config,
                    max_pend_time,
                )

        if site_config.lsfexecutors:
            for name in site_config.lsfexecutors:
                self.executors[f"{active_system}.lsf.{name}"] = LSFExecutor(
                    f"{active_system}.lsf.{name}",
                    site_config.target_config["executors"]["lsf"][name],
                    site_config,
                    max_pend_time,
                )

        if site_config.cobaltexecutors:
            for name in site_config.cobaltexecutors:
                self.executors[f"{active_system}.cobalt.{name}"] = CobaltExecutor(
                    f"{active_system}.cobalt.{name}",
                    site_config.target_config["executors"]["cobalt"][name],
                    site_config,
                    max_pend_time,
                )

        if site_config.pbsexecutors:
            for name in site_config.pbsexecutors:
                self.executors[f"{site_config.name()}.pbs.{name}"] = PBSExecutor(
                    f"{active_system}.pbs.{name}",
                    site_config.target_config["executors"]["pbs"][name],
                    site_config,
                    max_pend_time,
                )
        self.setup()

    def __str__(self):
        return "[buildtest-executor]"

    def __repr__(self):
        return "[buildtest-executor]"

    def list_executors(self):
        return list(self.executors.keys())

    def is_local(self, executor_type):
        return executor_type == "local"

    def is_slurm(self, executor_type):
        return executor_type == "slurm"

    def is_lsf(self, executor_type):
        return executor_type == "lsf"

    def is_pbs(self, executor_type):
        return executor_type == "pbs"

    def is_cobalt(self, executor_type):
        return executor_type == "cobalt"

    def get(self, name):
        """Given the name of an executor return the executor object which is of subclass of `BaseExecutor`"""
        return self.executors.get(name)

    def _choose_executor(self, builder):
        """Choose executor is called at the onset of a run and poll stage. Given a builder
        object we retrieve the executor property ``builder.executor`` of the builder and check if
        there is an executor object and of type `BaseExecutor`.

        :param builder: the builder with the loaded Buildspec.
        :type builder: BuilderBase (subclass), required.
        """

        # Get the executor by name, and add the builder to it
        executor = self.executors.get(builder.executor)
        if not isinstance(executor, BaseExecutor):
            raise ExecutorError(
                f"{executor} is not a valid executor because it is not of type BaseExecutor class."
            )

        return executor

    def setup(self):
        """This method creates directory ``var/executors/<executor-name>``
        for every executor defined in buildtest configuration and write scripts
        before_script.sh if the field ``before_script``
        is specified in executor section. This method
        is called after executors are initialized in the class **__init__**
        method.
        """

        for executor_name in self.executors.keys():
            create_dir(os.path.join(BUILDTEST_EXECUTOR_DIR, executor_name))
            executor_settings = self.executors[executor_name]._settings

            # if before_script field defined in executor section write content to var/executors/<executor>/before_script.sh
            file = os.path.join(
                BUILDTEST_EXECUTOR_DIR, executor_name, "before_script.sh"
            )
            content = executor_settings.get("before_script") or ""
            write_file(file, content)

    def load_builders(self, builders):
        """Adds builder objects into self.builders class variable. This method will only add objects that are instance of BuilderBase class"""
        for builder in builders:
            # only add items that are of class BuilderBase
            if not isinstance(builder, BuilderBase):
                continue

            executor = self._choose_executor(builder)
            executor.add_builder(builder)

            self.builders.append(builder)

    def run(self):
        """This method is responsible for running the build script for each builder async and
        gather the results. We setup a pool of worker settings by invoking ``multiprocessing.pool.Pool``
        and use ``multiprocessing.pool.Pool.apply_sync()`` method for running test async which returns
        an object of type ``multiprocessing.pool.AsyncResult`` which holds the result. Next we wait for
        results to arrive using ``multiprocessing.pool.AsyncResult.get()`` method in a infinite loop until
        all test results are retrieved. The return type is the same builder object which is added to list
        of valid builders that is returned at end of method.
        """

        results = []

        workers = mp.Pool(mp.cpu_count())

        for name in self.executors.keys():
            print(f"Name: {name}  Builders:  {self.executors[name].get_builder()}")

        # if there are no builders loaded we return from method
        if not self.builders:
            return

        for builder in self.builders:
            print("{:_<30}".format(""))
            print("Launching test:", builder.name)
            print("Test ID:", builder.test_uid)
            print("Executor Name:", builder.executor)
            print("Running Test: ", builder.build_script)

            executor = self._choose_executor(builder)
            if executor.type == "local":
                # local_builders.append(builder)
                result = workers.apply_async(executor.run, args=(builder,))
            else:
                # batch_builders.append(builder)
                result = workers.apply_async(executor.dispatch, args=(builder,))

            results.append(result)

        # loop until all async results  are complete. results is a list of multiprocessing.pool.AsyncResult objects
        while results:
            async_results_ready = []
            for result in results:
                try:
                    # line below will raise TimeoutError if result is not ready, if its ready we append item to list and break
                    task = result.get(0.1)
                except mp.TimeoutError:
                    continue

                async_results_ready.append(result)

                # the task object could be None if it fails to submit job therefore we only add items that are valid builders
                if isinstance(task, BuilderBase):
                    self.valid_builders.append(task)

            # remove result that are complete
            for result in async_results_ready:
                results.remove(result)

        # close the worker pool by preventing any more tasks from being submitted
        workers.close()

        # terminate all worker processes
        workers.join()

        return self.valid_builders

    def get_builders(self):
        """Return a list of valid builders that were run"""
        return self.valid_builders
