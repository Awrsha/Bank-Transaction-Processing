# Mojo Installation Guide for Windows

## Overview

This guide walks you through the process of installing Mojo, a language for programming high-performance systems, on a Windows machine. Since Mojo currently requires a Linux environment, this installation uses the Windows Subsystem for Linux (WSL).

## Prerequisites

To install Mojo on Windows, ensure you have:
- **Windows 10 version 2004** or higher.
- **Virtualization** enabled in your BIOS.

## Step-by-Step Installation

### 1. Install Windows Subsystem for Linux (WSL)

Mojo requires a Linux environment, so we’ll first install WSL.

1. Open **PowerShell** as Administrator and run:

   ```powershell
   wsl --install
   ```

2. Restart your computer to complete the installation.

3. After restarting, open **WSL** (Ubuntu) from the Start menu or by running:

   ```powershell
   wsl
   ```

### 2. Install Mojo within WSL

Once inside the WSL (Ubuntu) terminal, follow these steps:

1. **Update package list**:
   
   ```bash
   sudo apt update
   ```

2. **Install curl** (if not already installed):

   ```bash
   sudo apt install curl -y
   ```

3. **Download and install Mojo**:

   ```bash
   curl https://get.modular.com | sh
   ```

4. **Add Modular to your PATH**:

   ```bash
   export MODULAR_HOME="$HOME/.modular"
   export PATH="$MODULAR_HOME/pkg/packages.modular.com_mojo/bin:$PATH"
   ```

5. **Install Mojo**:

   ```bash
   modular install mojo
   ```

6. **Verify installation**:

   ```bash
   mojo --version
   ```

### 3. Persist PATH Settings

To make the PATH changes permanent:

1. Add the following lines to your `~/.bashrc`:

   ```bash
   echo 'export MODULAR_HOME="$HOME/.modular"' >> ~/.bashrc
   echo 'export PATH="$MODULAR_HOME/pkg/packages.modular.com_mojo/bin:$PATH"' >> ~/.bashrc
   ```

2. Apply the changes by running:

   ```bash
   source ~/.bashrc
   ```

## Important Notes

1. **Using Mojo in WSL**: Mojo can only be run within the WSL environment, not directly from Windows.
2. **Check WSL 2 Compatibility**: To confirm your system meets WSL 2 requirements, run the following in PowerShell:

   ```powershell
   systeminfo.exe | find "System Type"
   systeminfo.exe | find "BIOS Mode"
   ```
Finally. **Compile & Run**:
   ```powershell
   mojo build transaction_processor.mojo
   ./transaction_processor
   ```

**Note**: Ensure that virtualization is enabled in your system’s BIOS.

## Additional Assistance

If you encounter issues, consider:
- **Troubleshooting WSL installation**: Microsoft’s documentation provides [comprehensive support for WSL](https://docs.microsoft.com/en-us/windows/wsl/).
- **Setting up Mojo in VSCode**: To streamline development, VSCode offers extensions for WSL support.
- **Alternative solutions**: For optimization approaches that don’t require Mojo, feel free to explore similar high-performance tools available for native Windows environments.
