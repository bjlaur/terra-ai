FROM archlinux:latest

# Install system dependencies
RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm git sudo base-devel python && \
    echo 'terra-ai ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers.d/terra-ai

# Create non-root user
RUN useradd -m -u 1000 terra-ai && \
    chown -R terra-ai:terra-ai /home/terra-ai

USER terra-ai
WORKDIR /home/terra-ai

# Install yay
RUN git clone https://aur.archlinux.org/yay.git /tmp/yay && \
    cd /tmp/yay && makepkg -si --noconfirm && \
    rm -rf /tmp/yay

# Install Python packages from repos
RUN sudo pacman -S --noconfirm python-openai python-yaml python-httpx python-aiohttp python-beautifulsoup4 python-dotenv irssi

# Install sopel from AUR
RUN yay -S --needed --noconfirm sopel

# Remove NOPASSWD after yay build
USER root
RUN rm /etc/sudoers.d/terra-ai
USER terra-ai

# Copy plugin
COPY . .

VOLUME ["/home/terra-ai/data"]
ENTRYPOINT ["sopel", "-c", "config/terraai.yaml"]
