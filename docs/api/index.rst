SecAudit+ API Documentation
============================

Welcome to SecAudit+ API documentation. This documentation covers the internal modules and APIs.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   modules/modules
   modules/secaudit
   modules/seclib
   modules/utils

Overview
--------

SecAudit+ is a command-line security audit tool for GNU/Linux systems with YAML-based profiles.

Key Features
~~~~~~~~~~~~

* **Agentless Audit**: Execute audits over SSH without installing on target hosts
* **Extensible Profiles**: YAML-based profiles with inheritance and templating
* **Multiple Report Formats**: JSON, HTML, Markdown, SARIF, JUnit, Prometheus, Elastic
* **Compliance Coverage**: ФСТЭК, CIS Benchmarks, Custom policies
* **Sensitive Data Redaction**: Automatic redaction of credentials and secrets
* **Network Scanning**: Discover hosts with OS detection

Installation
------------

.. code-block:: bash

   git clone https://github.com/alexbergh/secaudit-plus.git
   cd secaudit-plus
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .

Quick Start
-----------

.. code-block:: bash

   # Check system health
   secaudit health

   # Validate profile
   secaudit validate --profile profiles/base/linux.yml

   # Run audit
   secaudit audit --profile profiles/base/server.yml --level strict

API Reference
-------------

Core Modules
~~~~~~~~~~~~

* :doc:`modules/modules` - Audit execution, reporting, and CLI
* :doc:`modules/secaudit` - Main CLI entry point and exceptions
* :doc:`modules/seclib` - Security utilities and validation
* :doc:`modules/utils` - Logging and utilities

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
